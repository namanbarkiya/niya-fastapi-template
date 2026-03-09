"""
Organization routes: CRUD orgs, manage members, invites.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.shared.models.user import User
from app.shared.schemas.org import (
    AcceptInviteRequest,
    ChangeRoleRequest,
    CreateOrgRequest,
    InviteMemberRequest,
    InviteResponse,
    MembershipResponse,
    OrgResponse,
    OrgWithRoleResponse,
    UpdateOrgRequest,
)
from app.shared.services.org_service import OrgService

router = APIRouter()


@router.post("", response_model=OrgResponse, status_code=201)
async def create_org(
    payload: CreateOrgRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.create_org(payload, current_user.id)


@router.get("", response_model=list[OrgWithRoleResponse])
async def list_my_orgs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.list_user_orgs(current_user.id)


@router.get("/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.get_org(org_id)


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_org(
    org_id: uuid.UUID,
    payload: UpdateOrgRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.update_org(org_id, current_user.id, payload)


@router.get("/{org_id}/members", response_model=list[MembershipResponse])
async def list_members(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.get_members(org_id, current_user.id)


@router.post("/{org_id}/invites", response_model=InviteResponse, status_code=201)
async def invite_member(
    org_id: uuid.UUID,
    payload: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.invite_member(
        org_id, current_user.id, payload.email, payload.role
    )


@router.post("/invites/accept", response_model=MembershipResponse)
async def accept_invite(
    payload: AcceptInviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.accept_invite(payload.token, current_user.id)


@router.delete("/{org_id}/members/{user_id}")
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.remove_member(org_id, current_user.id, user_id)


@router.patch("/{org_id}/members/{user_id}/role")
async def change_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ChangeRoleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = OrgService(db)
    return await svc.change_role(org_id, current_user.id, user_id, payload.role)
