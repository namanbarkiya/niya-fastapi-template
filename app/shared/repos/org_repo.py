"""
Organization repository — orgs + memberships + invites.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.models.org import OrgInvite, OrgMembership, Organization


class OrgRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Organizations
    # ------------------------------------------------------------------
    async def get_by_id(self, org_id: uuid.UUID) -> Optional[Organization]:
        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        result = await self.session.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        slug: str,
        created_by: uuid.UUID,
        logo_url: str | None = None,
    ) -> Organization:
        org = Organization(
            name=name, slug=slug, created_by=created_by, logo_url=logo_url
        )
        self.session.add(org)
        await self.session.flush()
        return org

    async def update(self, org_id: uuid.UUID, **kwargs) -> Optional[Organization]:
        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            update(Organization).where(Organization.id == org_id).values(**kwargs)
        )
        return await self.get_by_id(org_id)

    async def list_user_orgs(self, user_id: uuid.UUID) -> list[OrgMembership]:
        result = await self.session.execute(
            select(OrgMembership)
            .where(OrgMembership.user_id == user_id)
            .options(selectinload(OrgMembership.organization))
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Memberships
    # ------------------------------------------------------------------
    async def add_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID, role: str = "member"
    ) -> OrgMembership:
        membership = OrgMembership(org_id=org_id, user_id=user_id, role=role)
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_membership(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[OrgMembership]:
        result = await self.session.execute(
            select(OrgMembership).where(
                OrgMembership.org_id == org_id,
                OrgMembership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_members(self, org_id: uuid.UUID) -> list[OrgMembership]:
        result = await self.session.execute(
            select(OrgMembership).where(OrgMembership.org_id == org_id)
        )
        return list(result.scalars().all())

    async def change_role(
        self, org_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> None:
        await self.session.execute(
            update(OrgMembership)
            .where(
                OrgMembership.org_id == org_id,
                OrgMembership.user_id == user_id,
            )
            .values(role=role, updated_at=datetime.now(timezone.utc))
        )

    async def remove_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        membership = await self.get_membership(org_id, user_id)
        if membership:
            await self.session.delete(membership)
            await self.session.flush()

    # ------------------------------------------------------------------
    # Invites
    # ------------------------------------------------------------------
    async def create_invite(
        self,
        org_id: uuid.UUID,
        email: str,
        role: str,
        token: str,
        invited_by: uuid.UUID,
        expire_days: int = 7,
    ) -> OrgInvite:
        invite = OrgInvite(
            org_id=org_id,
            email=email.lower(),
            role=role,
            token=token,
            invited_by=invited_by,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expire_days),
        )
        self.session.add(invite)
        await self.session.flush()
        return invite

    async def get_invite_by_token(self, token: str) -> Optional[OrgInvite]:
        result = await self.session.execute(
            select(OrgInvite)
            .where(
                OrgInvite.token == token,
                OrgInvite.accepted_at.is_(None),
                OrgInvite.expires_at > datetime.now(timezone.utc),
            )
            .options(selectinload(OrgInvite.organization))
        )
        return result.scalar_one_or_none()

    async def get_org_invites(self, org_id: uuid.UUID) -> list[OrgInvite]:
        result = await self.session.execute(
            select(OrgInvite).where(
                OrgInvite.org_id == org_id,
                OrgInvite.accepted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def accept_invite(self, invite_id: uuid.UUID) -> None:
        await self.session.execute(
            update(OrgInvite)
            .where(OrgInvite.id == invite_id)
            .values(accepted_at=datetime.now(timezone.utc))
        )
