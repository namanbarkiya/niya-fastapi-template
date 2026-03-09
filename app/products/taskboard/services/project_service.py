"""
ProjectService — business logic for taskboard projects.

CROSS-SCHEMA PATTERN:
  This service accesses TWO schemas: "shared" (user validation) and
  "taskboard" (project/task data). They are NEVER joined. Always two
  separate queries through their respective repos.
"""
import uuid

from app.core.exceptions import AuthorizationError, NotFoundError
from app.products.taskboard.repos.project_repo import ProjectRepo
from app.products.taskboard.schemas.project import (
    CreateProjectRequest,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.shared.repos.user_repo import UserRepo


class ProjectService:
    def __init__(self, user_repo: UserRepo, project_repo: ProjectRepo) -> None:
        self.users = user_repo        # shared schema
        self.projects = project_repo  # taskboard schema

    async def list_projects(
        self, user_id: uuid.UUID, include_archived: bool = False
    ) -> list[ProjectResponse]:
        projects = await self.projects.list_by_user(
            user_id, include_archived=include_archived
        )
        return [ProjectResponse.model_validate(p) for p in projects]

    async def get_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> ProjectResponse:
        project = await self._get_owned(user_id, project_id)
        return ProjectResponse.model_validate(project)

    async def create_project(
        self, user_id: uuid.UUID, payload: CreateProjectRequest
    ) -> ProjectResponse:
        # Cross-schema lookup: verify user exists (shared.users)
        user = await self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        # Write to product schema (taskboard.projects)
        project = await self.projects.create(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            color=payload.color,
        )
        return ProjectResponse.model_validate(project)

    async def update_project(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        payload: UpdateProjectRequest,
    ) -> ProjectResponse:
        await self._get_owned(user_id, project_id)
        updated = await self.projects.update(
            project_id,
            name=payload.name,
            description=payload.description,
            color=payload.color,
        )
        return ProjectResponse.model_validate(updated)

    async def archive_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> dict:
        await self._get_owned(user_id, project_id)
        await self.projects.archive(project_id)
        return {"status": "success", "message": "Project archived"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_owned(self, user_id: uuid.UUID, project_id: uuid.UUID):
        project = await self.projects.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project not found")
        if project.user_id != user_id:
            raise AuthorizationError("You do not own this project")
        return project
