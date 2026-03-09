"""
AdminDashboardService — cross-product aggregate data for org admins.

ARCHITECTURE NOTE — why this lives in shared/:
  This service deliberately imports repos from multiple product modules.
  That is only allowed here in shared/ — products themselves may never
  import from each other. See CLAUDE.md §"Product modules never import
  from each other."

QUERY PATTERN — no cross-schema joins, ever:
  1. Query shared schema (users, org members)          → Python objects
  2. Query product_alpha schema (resources)            → Python objects
  3. Query taskboard schema (projects, tasks)          → Python objects
  4. Combine all results in Python                     → response model

  Each step is a separate async DB call. Steps can run concurrently
  (asyncio.gather) because they touch different schemas / tables.

GRACEFUL DEGRADATION:
  When a product is extracted to its own database, its data simply won't
  be available here. Replace the direct repo call with an HTTP call to the
  extracted service's /admin/stats endpoint, or omit the section entirely.
  The rest of the dashboard is unaffected.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.shared.models.user import User
from app.shared.repos.org_repo import OrgRepo
from app.shared.repos.user_repo import UserRepo
from app.shared.schemas.dashboard import (
    AdminDashboardResponse,
    MemberActivity,
    PlatformStats,
    ProductAlphaStats,
    ProductStats,
    TaskboardStats,
)

# ── Product repo imports — allowed because this module lives in shared/ ──────
from app.products.product_alpha.models.resource import Resource
from app.products.taskboard.models.project import Project
from app.products.taskboard.models.task import Task

logger = logging.getLogger(__name__)


class AdminDashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepo(db)
        self.org_repo = OrgRepo(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_dashboard(
        self,
        requesting_user_id: uuid.UUID,
        org_id: uuid.UUID | None = None,
    ) -> AdminDashboardResponse:
        """
        Build the admin dashboard response.

        If org_id is given, verifies the requesting user is owner/admin of
        that org, then scopes member-level activity to org members.

        If org_id is None, the platform-wide view is returned (no
        per-member breakdown, only aggregate counters).
        """
        org_name: str | None = None
        member_ids: list[uuid.UUID] = []

        if org_id:
            # Verify caller is org admin/owner
            membership = await self.org_repo.get_membership(org_id, requesting_user_id)
            if not membership or membership.role not in ("owner", "admin"):
                raise AuthorizationError(
                    "You must be an org owner or admin to view the dashboard"
                )

            org = await self.org_repo.get_by_id(org_id)
            if not org:
                raise NotFoundError("Organisation not found")
            org_name = org.name

            memberships = await self.org_repo.get_members(org_id)
            member_ids = [m.user_id for m in memberships]
        else:
            # Platform-wide: no per-member breakdown
            pass

        # Run all aggregate queries concurrently — each hits a different schema
        platform_task = self._platform_stats()
        alpha_task = self._product_alpha_stats(member_ids or None)
        taskboard_task = self._taskboard_stats(member_ids or None)

        platform, alpha_stats, taskboard_stats = await asyncio.gather(
            platform_task, alpha_task, taskboard_task
        )

        # Build per-member activity (only when org_id is given)
        members: list[MemberActivity] = []
        if org_id and member_ids:
            members = await self._member_activity(org_id, member_ids)

        return AdminDashboardResponse(
            org_id=org_id,
            org_name=org_name,
            generated_at=datetime.now(timezone.utc),
            platform=platform,
            products=ProductStats(
                product_alpha=alpha_stats,
                taskboard=taskboard_stats,
            ),
            members=members,
        )

    # ------------------------------------------------------------------
    # Shared schema — platform stats
    # ------------------------------------------------------------------

    async def _platform_stats(self) -> PlatformStats:
        """Count users from shared.users — one aggregate query."""
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        result = await self.db.execute(
            select(
                func.count(User.id).label("total"),
                func.count(User.id)
                .filter(User.last_login_at >= thirty_days_ago)
                .label("active"),
                func.count(User.id)
                .filter(User.email_verified.is_(True))
                .label("verified"),
            )
        )
        row = result.one()
        return PlatformStats(
            total_users=row.total or 0,
            active_users=row.active or 0,
            verified_users=row.verified or 0,
        )

    # ------------------------------------------------------------------
    # product_alpha schema — resource stats
    # ------------------------------------------------------------------

    async def _product_alpha_stats(
        self, user_ids: list[uuid.UUID] | None
    ) -> ProductAlphaStats:
        """
        Count resources from product_alpha.resources.
        Scoped to user_ids when provided (org members only).

        SEPARATE QUERY — no join to shared.users.
        """
        base = select(
            func.count(Resource.id).label("total"),
            func.count(Resource.id)
            .filter(Resource.is_active.is_(True))
            .label("active"),
        )
        if user_ids:
            base = base.where(Resource.user_id.in_(user_ids))

        result = await self.db.execute(base)
        row = result.one()
        return ProductAlphaStats(
            total_resources=row.total or 0,
            active_resources=row.active or 0,
        )

    # ------------------------------------------------------------------
    # taskboard schema — project + task stats
    # ------------------------------------------------------------------

    async def _taskboard_stats(
        self, user_ids: list[uuid.UUID] | None
    ) -> TaskboardStats:
        """
        Aggregate project + task counts from taskboard schema.
        Two separate queries (projects, tasks) — no joins to other schemas.
        """
        now = datetime.now(timezone.utc)

        # -- Projects --
        proj_stmt = select(
            func.count(Project.id).label("total"),
            func.count(Project.id)
            .filter(Project.is_archived.is_(False))
            .label("active"),
        )
        if user_ids:
            proj_stmt = proj_stmt.where(Project.user_id.in_(user_ids))

        proj_result = await self.db.execute(proj_stmt)
        proj_row = proj_result.one()

        # -- Tasks by status --
        task_stmt = select(Task.status, func.count(Task.id).label("cnt")).group_by(
            Task.status
        )
        if user_ids:
            # Scope to tasks created by org members
            task_stmt = task_stmt.where(Task.created_by.in_(user_ids))

        task_result = await self.db.execute(task_stmt)
        tasks_by_status = {row.status: row.cnt for row in task_result.all()}

        # -- Overdue tasks --
        overdue_stmt = select(func.count(Task.id)).where(
            Task.due_at < now,
            Task.status.not_in(["done", "canceled"]),
        )
        if user_ids:
            overdue_stmt = overdue_stmt.where(Task.created_by.in_(user_ids))

        overdue_result = await self.db.execute(overdue_stmt)
        overdue_count = overdue_result.scalar() or 0

        return TaskboardStats(
            total_projects=proj_row.total or 0,
            active_projects=proj_row.active or 0,
            tasks_by_status=tasks_by_status,
            overdue_tasks=overdue_count,
        )

    # ------------------------------------------------------------------
    # Per-member activity — three separate queries, combined in Python
    # ------------------------------------------------------------------

    async def _member_activity(
        self, org_id: uuid.UUID, member_ids: list[uuid.UUID]
    ) -> list[MemberActivity]:
        """
        Build a per-member activity summary by running three queries:
          1. shared.users             — email + last_login_at
          2. product_alpha.resources  — resource count per user
          3. taskboard.projects       — project count per user
          4. taskboard.tasks          — open task count per user

        NO cross-schema joins. Results are combined in Python.
        """
        if not member_ids:
            return []

        # Query 1: user info (shared schema)
        memberships = await self.org_repo.get_members(org_id)
        membership_by_uid = {m.user_id: m.role for m in memberships}

        users_result = await self.db.execute(
            select(User.id, User.email, User.last_login_at).where(
                User.id.in_(member_ids)
            )
        )
        user_rows = {row.id: row for row in users_result.all()}

        # Query 2: product_alpha resource counts (product_alpha schema)
        alpha_result = await self.db.execute(
            select(Resource.user_id, func.count(Resource.id).label("cnt"))
            .where(Resource.user_id.in_(member_ids), Resource.is_active.is_(True))
            .group_by(Resource.user_id)
        )
        alpha_counts: dict[uuid.UUID, int] = {
            row.user_id: row.cnt for row in alpha_result.all()
        }

        # Query 3: taskboard project counts (taskboard schema)
        proj_result = await self.db.execute(
            select(Project.user_id, func.count(Project.id).label("cnt"))
            .where(
                Project.user_id.in_(member_ids),
                Project.is_archived.is_(False),
            )
            .group_by(Project.user_id)
        )
        proj_counts: dict[uuid.UUID, int] = {
            row.user_id: row.cnt for row in proj_result.all()
        }

        # Query 4: taskboard open task counts (taskboard schema)
        open_task_result = await self.db.execute(
            select(Task.created_by, func.count(Task.id).label("cnt"))
            .where(
                Task.created_by.in_(member_ids),
                Task.status.in_(["todo", "in_progress"]),
            )
            .group_by(Task.created_by)
        )
        open_task_counts: dict[uuid.UUID, int] = {
            row.created_by: row.cnt for row in open_task_result.all()
        }

        # Combine in Python — no SQL JOINs
        activity: list[MemberActivity] = []
        for uid in member_ids:
            user_row = user_rows.get(uid)
            if not user_row:
                continue
            activity.append(
                MemberActivity(
                    user_id=uid,
                    email=user_row.email,
                    role=membership_by_uid.get(uid, "member"),
                    last_login_at=user_row.last_login_at,
                    alpha_resources=alpha_counts.get(uid, 0),
                    taskboard_projects=proj_counts.get(uid, 0),
                    taskboard_open_tasks=open_task_counts.get(uid, 0),
                )
            )
        return activity
