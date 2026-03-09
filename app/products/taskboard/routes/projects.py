"""
taskboard project routes.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.products.taskboard.repos.project_repo import ProjectRepo
from app.products.taskboard.schemas.project import (
    CreateProjectRequest,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.products.taskboard.services.project_service import ProjectService
from app.shared.models.user import User
from app.shared.repos.user_repo import UserRepo

router = APIRouter()


def _svc(db: AsyncSession) -> ProjectService:
    return ProjectService(UserRepo(db), ProjectRepo(db))


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).list_projects(current_user.id, include_archived=include_archived)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).create_project(current_user.id, payload)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).get_project(current_user.id, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    payload: UpdateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).update_project(current_user.id, project_id, payload)


@router.post("/{project_id}/archive")
async def archive_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).archive_project(current_user.id, project_id)
