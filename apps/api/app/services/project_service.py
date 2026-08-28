"""Project business logic with strict per-user ownership (SECURITY.md §2)."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, user_id: uuid.UUID, title: str | None, brief: dict[str, Any]
    ) -> Project:
        project = Project(user_id=user_id, title=title, brief=brief or {}, status="draft")
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def get_owned(self, user_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        """Fetch a project only if it belongs to the user and isn't deleted.

        Returns None on miss so the route can 404 without revealing existence.
        """
        return await self.db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
                Project.deleted_at.is_(None),
            )
        )

    async def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        result = await self.db.scalars(
            select(Project)
            .where(Project.user_id == user_id, Project.deleted_at.is_(None))
            .order_by(Project.updated_at.desc())
        )
        return list(result)

    async def update_brief(
        self,
        project: Project,
        title: str | None,
        brief: dict[str, Any] | None,
    ) -> Project:
        """Auto-save: shallow-merge the incoming brief into the stored one."""
        if title is not None:
            project.title = title
        if brief is not None:
            merged = dict(project.brief or {})
            merged.update(brief)
            project.brief = merged
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def soft_delete(self, project: Project) -> None:
        from datetime import UTC, datetime

        project.deleted_at = datetime.now(UTC)
        await self.db.commit()
