"""Project ownership isolation tests (SECURITY.md §2 — IDOR prevention).

Requires the Postgres dev stack: `make test-api`.
"""

import uuid

import pytest

from app.models import User
from app.services.project_service import ProjectService

pytestmark = pytest.mark.asyncio


async def _make_user(db) -> User:
    user = User(email=f"owner-{uuid.uuid4().hex[:8]}@example.com", is_active=True)
    db.add(user)
    await db.flush()
    return user


class TestOwnershipIsolation:
    async def test_owner_can_load_own_project(self, db):
        owner = await _make_user(db)
        service = ProjectService(db)
        project = await service.create(owner.id, "Mine", {"brand": {"name": "Acme"}})

        loaded = await service.get_owned(owner.id, project.id)
        assert loaded is not None
        assert loaded.id == project.id

    async def test_other_user_cannot_load_project(self, db):
        owner = await _make_user(db)
        intruder = await _make_user(db)
        service = ProjectService(db)
        project = await service.create(owner.id, "Mine", {})

        assert await service.get_owned(intruder.id, project.id) is None

    async def test_unknown_project_id_returns_none(self, db):
        user = await _make_user(db)
        assert await ProjectService(db).get_owned(user.id, uuid.uuid4()) is None

    async def test_listing_only_returns_own_projects(self, db):
        owner = await _make_user(db)
        other = await _make_user(db)
        service = ProjectService(db)
        await service.create(owner.id, "A", {})
        await service.create(owner.id, "B", {})
        await service.create(other.id, "C", {})

        mine = await service.list_for_user(owner.id)
        assert {p.title for p in mine} == {"A", "B"}


class TestSoftDelete:
    async def test_deleted_project_is_not_returned(self, db):
        owner = await _make_user(db)
        service = ProjectService(db)
        project = await service.create(owner.id, "Temp", {})

        await service.soft_delete(project)

        assert await service.get_owned(owner.id, project.id) is None

    async def test_deleted_project_is_excluded_from_list(self, db):
        owner = await _make_user(db)
        service = ProjectService(db)
        keep = await service.create(owner.id, "Keep", {})
        drop = await service.create(owner.id, "Drop", {})
        await service.soft_delete(drop)

        titles = {p.title for p in await service.list_for_user(owner.id)}
        assert titles == {"Keep"}
        assert keep.deleted_at is None

    async def test_soft_delete_sets_timestamp_not_row_removal(self, db):
        owner = await _make_user(db)
        service = ProjectService(db)
        project = await service.create(owner.id, "Temp", {})
        await service.soft_delete(project)
        assert project.deleted_at is not None


class TestBriefAutoSave:
    async def test_brief_updates_merge_rather_than_replace(self, db):
        owner = await _make_user(db)
        service = ProjectService(db)
        project = await service.create(owner.id, None, {"brand": {"name": "Acme"}})

        await service.update_brief(project, None, {"product": {"name": "Widget"}})

        assert project.brief["brand"] == {"name": "Acme"}
        assert project.brief["product"] == {"name": "Widget"}

    async def test_same_section_is_overwritten(self, db):
        owner = await _make_user(db)
        service = ProjectService(db)
        project = await service.create(owner.id, None, {"brand": {"name": "Old"}})

        await service.update_brief(project, None, {"brand": {"name": "New"}})

        assert project.brief["brand"]["name"] == "New"

    async def test_title_can_be_updated_independently(self, db):
        owner = await _make_user(db)
        service = ProjectService(db)
        project = await service.create(owner.id, "Original", {})

        await service.update_brief(project, "Renamed", None)

        assert project.title == "Renamed"
