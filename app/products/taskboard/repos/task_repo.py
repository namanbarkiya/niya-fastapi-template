"""
Repository for taskboard Tasks.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.products.taskboard.models.task import Task


class TaskRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, task_id: uuid.UUID) -> Task | None:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(
        self, project_id: uuid.UUID, status: str | None = None
    ) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.project_id == project_id)
            .order_by(Task.priority.desc(), Task.created_at.asc())
        )
        if status:
            stmt = stmt.where(Task.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_assigned_to(self, user_id: uuid.UUID) -> list[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.assigned_to == user_id, Task.status != "done")
            .order_by(Task.priority.desc(), Task.due_at.asc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        project_id: uuid.UUID,
        created_by: uuid.UUID,
        title: str,
        description: str | None = None,
        status: str = "todo",
        priority: int = 0,
        assigned_to: uuid.UUID | None = None,
        due_at: datetime | None = None,
    ) -> Task:
        task = Task(
            project_id=project_id,
            created_by=created_by,
            title=title,
            description=description,
            status=status,
            priority=priority,
            assigned_to=assigned_to,
            due_at=due_at,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def update(self, task_id: uuid.UUID, **kwargs) -> Task | None:
        # If status is changing to "done", stamp completed_at
        if kwargs.get("status") == "done":
            kwargs.setdefault("completed_at", datetime.now(timezone.utc))
        elif "status" in kwargs and kwargs["status"] != "done":
            kwargs["completed_at"] = None
        values = {k: v for k, v in kwargs.items() if v is not None}
        if values:
            await self.session.execute(
                update(Task).where(Task.id == task_id).values(**values)
            )
            await self.session.flush()
        return await self.get_by_id(task_id)

    async def delete(self, task_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Task).where(Task.id == task_id).values(status="canceled")
        )
        await self.session.flush()
