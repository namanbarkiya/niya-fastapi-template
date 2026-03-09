"""
Organization service — create org, invite/accept/remove members, change roles.
"""
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import generate_secure_token
from app.shared.repos.org_repo import OrgRepo
from app.shared.repos.user_repo import UserRepo
from app.shared.schemas.org import (
    CreateOrgRequest,
    InviteResponse,
    MembershipResponse,
    OrgResponse,
    OrgWithRoleResponse,
    UpdateOrgRequest,
)

logger = logging.getLogger(__name__)


class OrgService:
    def __init__(self, db: AsyncSession) -> None:
        self.org_repo = OrgRepo(db)
        self.user_repo = UserRepo(db)

    async def create_org(
        self, payload: CreateOrgRequest, user_id: UUID
    ) -> OrgResponse:
        existing = await self.org_repo.get_by_slug(payload.slug)
        if existing:
            raise ConflictError("An organization with this slug already exists")

        org = await self.org_repo.create(
            name=payload.name,
            slug=payload.slug,
            created_by=user_id,
            logo_url=payload.logo_url,
        )
        # Creator becomes owner
        await self.org_repo.add_member(org.id, user_id, role="owner")
        logger.info(f"Org created: {org.id} by user {user_id}")
        return OrgResponse.model_validate(org)

    async def get_org(self, org_id: UUID) -> OrgResponse:
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization not found")
        return OrgResponse.model_validate(org)

    async def update_org(
        self, org_id: UUID, user_id: UUID, payload: UpdateOrgRequest
    ) -> OrgResponse:
        await self._require_role(org_id, user_id, ["owner", "admin"])
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            org = await self.org_repo.get_by_id(org_id)
        else:
            org = await self.org_repo.update(org_id, **updates)
        if not org:
            raise NotFoundError("Organization not found")
        return OrgResponse.model_validate(org)

    async def list_user_orgs(self, user_id: UUID) -> list[OrgWithRoleResponse]:
        memberships = await self.org_repo.list_user_orgs(user_id)
        return [
            OrgWithRoleResponse(
                org=OrgResponse.model_validate(m.organization),
                role=m.role,
            )
            for m in memberships
        ]

    async def get_members(
        self, org_id: UUID, user_id: UUID
    ) -> list[MembershipResponse]:
        await self._require_membership(org_id, user_id)
        members = await self.org_repo.get_members(org_id)
        return [MembershipResponse.model_validate(m) for m in members]

    async def invite_member(
        self,
        org_id: UUID,
        inviter_id: UUID,
        email: str,
        role: str = "member",
    ) -> InviteResponse:
        await self._require_role(org_id, inviter_id, ["owner", "admin"])

        # Check if user is already a member
        user = await self.user_repo.get_by_email(email)
        if user:
            existing = await self.org_repo.get_membership(org_id, user.id)
            if existing:
                raise ConflictError("User is already a member of this organization")

        token = generate_secure_token()
        invite = await self.org_repo.create_invite(
            org_id=org_id,
            email=email,
            role=role,
            token=token,
            invited_by=inviter_id,
        )
        logger.info(f"Invite sent for org {org_id} to {email}")
        return InviteResponse.model_validate(invite)

    async def accept_invite(self, token: str, user_id: UUID) -> MembershipResponse:
        invite = await self.org_repo.get_invite_by_token(token)
        if not invite:
            raise ValidationError("Invite is invalid or expired")

        # Check not already a member
        existing = await self.org_repo.get_membership(invite.org_id, user_id)
        if existing:
            raise ConflictError("You are already a member of this organization")

        await self.org_repo.accept_invite(invite.id)
        membership = await self.org_repo.add_member(
            invite.org_id, user_id, role=invite.role
        )
        logger.info(f"User {user_id} joined org {invite.org_id}")
        return MembershipResponse.model_validate(membership)

    async def remove_member(
        self, org_id: UUID, remover_id: UUID, target_user_id: UUID
    ) -> dict:
        await self._require_role(org_id, remover_id, ["owner", "admin"])

        target = await self.org_repo.get_membership(org_id, target_user_id)
        if not target:
            raise NotFoundError("Member not found")
        if target.role == "owner" and remover_id != target_user_id:
            raise AuthorizationError("Cannot remove the owner")

        await self.org_repo.remove_member(org_id, target_user_id)
        return {"status": "success", "message": "Member removed"}

    async def change_role(
        self, org_id: UUID, changer_id: UUID, target_user_id: UUID, role: str
    ) -> dict:
        await self._require_role(org_id, changer_id, ["owner"])
        target = await self.org_repo.get_membership(org_id, target_user_id)
        if not target:
            raise NotFoundError("Member not found")
        await self.org_repo.change_role(org_id, target_user_id, role)
        return {"status": "success", "message": f"Role changed to {role}"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _require_membership(
        self, org_id: UUID, user_id: UUID
    ) -> None:
        membership = await self.org_repo.get_membership(org_id, user_id)
        if not membership:
            raise AuthorizationError("Not a member of this organization")

    async def _require_role(
        self, org_id: UUID, user_id: UUID, roles: list[str]
    ) -> None:
        membership = await self.org_repo.get_membership(org_id, user_id)
        if not membership or membership.role not in roles:
            raise AuthorizationError(
                f"Requires one of: {', '.join(roles)}"
            )
