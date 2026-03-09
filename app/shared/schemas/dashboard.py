"""
Pydantic schemas for the admin dashboard.

All response models are flat and serialisable — no lazy-loaded ORM objects.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Sub-sections of the dashboard
# ─────────────────────────────────────────────────────────────────────────────

class PlatformStats(BaseModel):
    """Platform-wide user counts (shared schema)."""
    total_users: int
    active_users: int          # logged in within last 30 days
    verified_users: int        # email_verified = True


class ProductAlphaStats(BaseModel):
    """
    Aggregate stats for product_alpha.
    Queried from product_alpha schema — separate query, never joined.

    When product_alpha is extracted to its own DB, this section will be
    replaced by an API call. The rest of the dashboard remains unaffected.
    """
    total_resources: int
    active_resources: int


class TaskboardStats(BaseModel):
    """
    Aggregate stats for taskboard.
    Queried from taskboard schema — separate query, never joined.
    """
    total_projects: int
    active_projects: int       # not archived
    tasks_by_status: dict[str, int]   # {"todo": N, "in_progress": N, "done": N}
    overdue_tasks: int         # due_at < now AND status not done/canceled


class ProductStats(BaseModel):
    """Container for all product stat blocks."""
    product_alpha: Optional[ProductAlphaStats] = None
    taskboard: Optional[TaskboardStats] = None


# ─────────────────────────────────────────────────────────────────────────────
# Per-member activity
# ─────────────────────────────────────────────────────────────────────────────

class MemberActivity(BaseModel):
    """Cross-product activity summary for a single org member."""
    user_id: uuid.UUID
    email: str
    role: str
    last_login_at: Optional[datetime] = None

    # product_alpha (product_alpha schema — separate query)
    alpha_resources: int = 0

    # taskboard (taskboard schema — separate query)
    taskboard_projects: int = 0
    taskboard_open_tasks: int = 0   # status in (todo, in_progress)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level response
# ─────────────────────────────────────────────────────────────────────────────

class AdminDashboardResponse(BaseModel):
    """
    Full admin dashboard response.

    Data is aggregated from multiple schemas via separate queries combined
    in Python. No cross-schema SQL joins are used anywhere.
    """
    org_id: Optional[uuid.UUID] = None
    org_name: Optional[str] = None
    generated_at: datetime
    platform: PlatformStats
    products: ProductStats
    members: list[MemberActivity]
