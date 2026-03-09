"""
TaskService — business logic for taskboard tasks.

Tasks live inside projects. We verify project ownership before operating
on tasks — one extra query, but it keeps authorization consistent.
"""
import uuid

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.products.taskboard.repos.project_repo import ProjectRepo
from app.products.taskboard.repos.task_repo import TaskRepo
from app.products.taskboard.schemas.task import (
    CreateTaskRequest,
    TaskResponse,
    UpdateTaskRequest,
)
from app.shared.repos.user_repo import UserRepo


class TaskService:
    def __init__(
        self,
        user_repo: UserRepo,
        project_repo: ProjectRepo,
        task_repo: TaskRepo,
    ) -> None:
        self.users = user_repo          # shared schema
        self.projects = project_repo    # taskboard schema
        self.tasks = task_repo          # taskboard schema

    async def list_tasks(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        status: str | None = None,
    ) -> list[TaskResponse]:
        await self._assert_project_owner(user_id, project_id)
        tasks = await self.tasks.list_by_project(project_id, status=status)
        return [TaskResponse.model_validate(t) for t in tasks]

    async def get_task(
        self, user_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID
    ) -> TaskResponse:
        await self._assert_project_owner(user_id, project_id)
        task = await self._get_task_in_project(task_id, project_id)
        return TaskResponse.model_validate(task)

    async def create_task(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        payload: CreateTaskRequest,
    ) -> TaskResponse:
        await self._assert_project_owner(user_id, project_id)

        # If assigning to someone else, verify they exist (cross-schema lookup)
        if payload.assigned_to and payload.assigned_to != user_id:
            assignee = await self.users.get_by_id(payload.assigned_to)
            if not assignee:
                raise NotFoundError("Assigned user not found")

        task = await self.tasks.create(
            project_id=project_id,
            created_by=user_id,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
            due_at=payload.due_at,
        )
        return TaskResponse.model_validate(task)

    async def update_task(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        payload: UpdateTaskRequest,
    ) -> TaskResponse:
        await self._assert_project_owner(user_id, project_id)
        await self._get_task_in_project(task_id, project_id)

        update_data = payload.model_dump(exclude_none=True)
        updated = await self.tasks.update(task_id, **update_data)
        return TaskResponse.model_validate(updated)

    async def delete_task(
        self, user_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID
    ) -> dict:
        await self._assert_project_owner(user_id, project_id)
        await self._get_task_in_project(task_id, project_id)
        await self.tasks.delete(task_id)
        return {"status": "success", "message": "Task canceled"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _assert_project_owner(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> None:
        project = await self.projects.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project not found")
        if project.user_id != user_id:
            raise AuthorizationError("You do not own this project")

    async def _get_task_in_project(
        self, task_id: uuid.UUID, project_id: uuid.UUID
    ):
        task = await self.tasks.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task not found")
        if task.project_id != project_id:
            raise ValidationError("Task does not belong to this project")
        return task
