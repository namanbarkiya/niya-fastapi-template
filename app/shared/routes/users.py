"""
User routes: GET /me, PATCH /me, GET /me/profile, PATCH /me/profile,
             GET /me/emails, POST /me/emails
"""
import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import ConflictError
from app.shared.models.user import User
from app.shared.repos.user_repo import UserRepo
from app.shared.schemas.auth import ChangePasswordRequest
from app.shared.schemas.user import (
    AddEmailRequest,
    EmailResponse,
    MeResponse,
    ProfileResponse,
    ProfileUpdate,
)
from app.shared.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.get_me(current_user)


@router.patch("/me", response_model=MeResponse)
async def update_me(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.update_profile(current_user, payload)


@router.get("/me/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepo(db)
    profile = await repo.get_profile(current_user.id)
    if not profile:
        profile = await repo.create_profile(current_user.id)
    return ProfileResponse.model_validate(profile)


@router.patch("/me/profile", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepo(db)
    updates = payload.model_dump(exclude_none=True)
    if updates:
        await repo.update_profile(current_user.id, updates)
    profile = await repo.get_profile(current_user.id)
    return ProfileResponse.model_validate(profile)


@router.get("/me/emails", response_model=list[EmailResponse])
async def get_emails(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepo(db)
    emails = await repo.get_emails(current_user.id)
    return [EmailResponse.model_validate(e) for e in emails]


@router.post("/me/emails", response_model=EmailResponse, status_code=201)
async def add_email(
    payload: AddEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepo(db)
    existing = await repo.get_email_by_address(payload.email)
    if existing:
        raise ConflictError("This email address is already in use")
    email_record = await repo.add_email(current_user.id, payload.email)
    return EmailResponse.model_validate(email_record)


@router.patch("/me/password")
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.change_password(
        current_user, payload.current_password, payload.new_password, response
    )
