"""
product_alpha resource routes.

Route layer is intentionally thin:
  1. Parse and validate the request (Pydantic handles this via type hints).
  2. Build dependencies (repos, service) from the injected DB session.
  3. Call the service method.
  4. Return the response.

No business logic lives here.
"""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.products.product_alpha.repos.resource_repo import ResourceRepo
from app.products.product_alpha.schemas.resource import (
    CreateResourceRequest,
    ResourceResponse,
    UpdateResourceRequest,
)
from app.products.product_alpha.services.resource_service import ResourceService
from app.shared.models.user import User
from app.shared.repos.user_repo import UserRepo

router = APIRouter()


def _service(db: AsyncSession) -> ResourceService:
    """Build the service with both repos sharing the same DB session."""
    return ResourceService(
        user_repo=UserRepo(db),
        resource_repo=ResourceRepo(db),
    )


@router.get("", response_model=list[ResourceResponse])
async def list_resources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).list_resources(current_user.id)


@router.post("", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_resource(
    payload: CreateResourceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).create_resource(current_user.id, payload)


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).get_resource(current_user.id, resource_id)


@router.patch("/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: uuid.UUID,
    payload: UpdateResourceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).update_resource(current_user.id, resource_id, payload)


@router.delete("/{resource_id}")
async def delete_resource(
    resource_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).delete_resource(current_user.id, resource_id)
