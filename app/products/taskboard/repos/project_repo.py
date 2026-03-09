"""
Repository for taskboard Projects.
"""
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.products.taskboard.models.project import Project


class ProjectRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        result = await self.session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: uuid.UUID, include_archived: bool = False
    ) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
        if not include_archived:
            stmt = stmt.where(Project.is_archived.is_(False))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        description: str | None = None,
        color: str | None = None,
    ) -> Project:
        project = Project(
            user_id=user_id,
            name=name,
            description=description,
            color=color,
        )
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def update(
        self,
        project_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        color: str | None = None,
    ) -> Project | None:
        values = {
            k: v for k, v in dict(name=name, description=description, color=color).items()
            if v is not None
        }
        if values:
            await self.session.execute(
                update(Project).where(Project.id == project_id).values(**values)
            )
            await self.session.flush()
        return await self.get_by_id(project_id)

    async def archive(self, project_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Project).where(Project.id == project_id).values(is_archived=True)
        )
        await self.session.flush()
