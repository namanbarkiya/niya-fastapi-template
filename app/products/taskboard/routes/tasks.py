"""
taskboard task routes.
Tasks are nested under projects: /projects/{project_id}/tasks/...
"""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.products.taskboard.repos.project_repo import ProjectRepo
from app.products.taskboard.repos.task_repo import TaskRepo
from app.products.taskboard.schemas.task import (
    CreateTaskRequest,
    TaskResponse,
    UpdateTaskRequest,
)
from app.products.taskboard.services.task_service import TaskService
from app.shared.models.user import User
from app.shared.repos.user_repo import UserRepo

router = APIRouter()


def _svc(db: AsyncSession) -> TaskService:
    return TaskService(UserRepo(db), ProjectRepo(db), TaskRepo(db))


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    project_id: uuid.UUID,
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).list_tasks(current_user.id, project_id, status=status)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: uuid.UUID,
    payload: CreateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).create_task(current_user.id, project_id, payload)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).get_task(current_user.id, project_id, task_id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: UpdateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).update_task(current_user.id, project_id, task_id, payload)


@router.delete("/{task_id}")
async def delete_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).delete_task(current_user.id, project_id, task_id)
