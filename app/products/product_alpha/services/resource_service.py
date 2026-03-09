"""
ResourceService — business logic for product_alpha resources.

CROSS-SCHEMA PATTERN (critical to understand):
  This service operates on TWO schemas: "shared" and "product_alpha".
  These are NEVER joined in SQL. Instead:

    1. Shared data (user info, billing) is fetched via shared repos.
    2. Product data (resources) is fetched via product repos.
    3. They are combined in Python, not in the database.

  This keeps the schemas decoupled and makes future extraction trivial.

DEPENDENCY INJECTION:
  The service receives both repos as constructor arguments.
  Routes create them from the same AsyncSession and pass them in.
  This makes the service fully testable with mocked repos.
"""
import uuid
from typing import Any

from app.core.exceptions import AuthorizationError, NotFoundError
from app.products.product_alpha.repos.resource_repo import ResourceRepo
from app.products.product_alpha.schemas.resource import (
    CreateResourceRequest,
    ResourceResponse,
    UpdateResourceRequest,
)
from app.shared.repos.user_repo import UserRepo


class ResourceService:
    def __init__(self, user_repo: UserRepo, resource_repo: ResourceRepo) -> None:
        # shared repo — for cross-schema user lookups (no JOIN, separate query)
        self.users = user_repo
        # product repo — all product_alpha data access
        self.resources = resource_repo

    async def list_resources(self, user_id: uuid.UUID) -> list[ResourceResponse]:
        """
        List all active resources for a user.

        We trust that user_id comes from the verified JWT — no need to
        re-validate the user exists on every list call. Reserve the user
        lookup for operations that need user data (e.g. email, name).
        """
        resources = await self.resources.list_by_user(user_id)
        return [ResourceResponse.model_validate(r) for r in resources]

    async def get_resource(
        self, user_id: uuid.UUID, resource_id: uuid.UUID
    ) -> ResourceResponse:
        resource = await self.resources.get_by_id(resource_id)
        if not resource or not resource.is_active:
            raise NotFoundError("Resource not found")
        # Ownership check — never skip this
        if resource.user_id != user_id:
            raise AuthorizationError("You do not own this resource")
        return ResourceResponse.model_validate(resource)

    async def create_resource(
        self, user_id: uuid.UUID, payload: CreateResourceRequest
    ) -> ResourceResponse:
        """
        Create a resource.

        CROSS-SCHEMA LOOKUP EXAMPLE:
          Here we verify the user exists in shared.users before writing to
          product_alpha.resources. This is two separate DB queries.
          Never write: SELECT r.*, u.email FROM product_alpha.resources r
                       JOIN shared.users u ON u.id = r.user_id  <-- FORBIDDEN
        """
        # Query 1: verify user exists (shared schema)
        user = await self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        # Query 2: create the product resource (product_alpha schema)
        resource = await self.resources.create(
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            data=payload.data,
        )
        return ResourceResponse.model_validate(resource)

    async def update_resource(
        self,
        user_id: uuid.UUID,
        resource_id: uuid.UUID,
        payload: UpdateResourceRequest,
    ) -> ResourceResponse:
        resource = await self.resources.get_by_id(resource_id)
        if not resource or not resource.is_active:
            raise NotFoundError("Resource not found")
        if resource.user_id != user_id:
            raise AuthorizationError("You do not own this resource")

        updated = await self.resources.update(
            resource_id,
            title=payload.title,
            description=payload.description,
            data=payload.data,
        )
        return ResourceResponse.model_validate(updated)

    async def delete_resource(
        self, user_id: uuid.UUID, resource_id: uuid.UUID
    ) -> dict:
        resource = await self.resources.get_by_id(resource_id)
        if not resource or not resource.is_active:
            raise NotFoundError("Resource not found")
        if resource.user_id != user_id:
            raise AuthorizationError("You do not own this resource")

        await self.resources.delete(resource_id)
        return {"status": "success", "message": "Resource deleted"}
