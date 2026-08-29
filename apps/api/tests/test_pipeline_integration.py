"""End-to-end pipeline test: brief -> script -> assets -> video -> stitch -> export.

This is the first test that asserts the *product* works rather than that units
work in isolation. It drives the real HTTP routes against the real database, so
ownership checks, schema validation, credit accounting, and the per-scene state
machine are all exercised together.

Runs entirely on mock providers, so it needs no API keys and costs nothing. The
mocks were built to reproduce the awkward parts of reality, which is what makes
this worth running:

* the video mock reports QUEUED, then RUNNING, then COMPLETED across successive
  polls, so the polling loop and status transitions genuinely run,
* the image mock writes a real decodable PNG,
* the video mock renders a real MP4 via ffmpeg, so stitching concatenates actual
  media rather than placeholder bytes,
* failures raise the same exception classes as the live adapters, so the retry
  and per-scene refund paths execute.

Requires Postgres, Redis, and ffmpeg. CI provides all three.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.adapters.factory import get_storage_adapter
from app.adapters.mock import mock_video
from app.db.session import get_db
from app.main import app
from app.models import CreditTransaction, Project, Scene, User, VideoModel, Wallet
from app.services.credit_service import CreditService
from app.services.stitch_service import StitchService
from app.utils.tokens import create_access_token

pytestmark = pytest.mark.asyncio

API = "/api/v1"

BRIEF = {
    "brand": {
        "name": "Northwind Coffee",
        "colors": ["#1B4332", "#D8F3DC"],
        "voice_tone": ["warm", "confident"],
    },
    "product": {
        "name": "Cold Brew Concentrate",
        "description": "Slow-steeped concentrate that makes one cup or twelve.",
    },
    "audience": {
        "description": "People who drink coffee at their desk and resent the queue.",
        "pain_points": ["queueing before work", "bitter reheated coffee"],
    },
    "campaign": {"format": "9:16", "objective": "awareness"},
}


@pytest.fixture
async def client(db):
    """HTTP client bound to the test transaction.

    Overriding `get_db` is what keeps the request handlers inside the same
    rolled-back transaction as the fixture, so the run leaves nothing behind.
    """

    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def funded_user(db):
    """A user with a wallet and enough credits to complete a run.

    Created directly rather than through `/auth/register` so the auth rate limit
    is not consumed by setup; a separate test covers the HTTP auth path.
    """
    user = User(
        email=f"pipeline-{uuid.uuid4().hex[:8]}@example.com",
        is_active=True,
        onboarding_completed=True,
    )
    db.add(user)
    await db.flush()
    db.add(Wallet(user_id=user.id, balance_credits=0))
    await db.flush()

    await CreditService(db).grant(
        user.id,
        Decimal("500"),
        transaction_type="purchase",
        count_as_purchase=True,
    )
    return user


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def show(response) -> str:
    """Response detail for assertion messages; 500s are otherwise opaque."""
    return f"{response.status_code} {response.text[:400]}"


async def cheapest_enabled_model(db) -> VideoModel:
    """Pick a real registry row, which also asserts the seed produced usable models."""
    rows = list(
        await db.scalars(
            select(VideoModel)
            .where(VideoModel.is_enabled.is_(True))
            .order_by(VideoModel.credit_multiplier)
        )
    )
    if not rows:
        pytest.skip("No enabled video models; run the seed script first.")
    return rows[0]


class TestFullPipeline:
    async def test_brief_to_export(self, client, db, funded_user):
        mock_video.reset_jobs()
        headers = auth(funded_user)
        credits = CreditService(db)
        starting_balance = await credits.get_balance(funded_user.id)

        # --- project + brief -------------------------------------------------
        created = await client.post(
            f"{API}/projects",
            json={"title": "Northwind cold brew launch"},
            headers=headers,
        )
        assert created.status_code == 201, show(created)
        project_id = created.json()["id"]

        saved = await client.patch(
            f"{API}/projects/{project_id}",
            json={"brief": BRIEF},
            headers=headers,
        )
        assert saved.status_code == 200, show(saved)
        assert saved.json()["brief"]["brand"]["name"] == "Northwind Coffee"

        # --- script ----------------------------------------------------------
        quoted = await client.get(f"{API}/projects/{project_id}/script/cost", headers=headers)
        assert quoted.status_code == 200, show(quoted)
        script_cost = Decimal(str(quoted.json()["credits_required"]))
        assert script_cost > 0

        generated = await client.post(
            f"{API}/projects/{project_id}/script",
            json={"ad_category": "problem-agitation-solution", "aspect_ratio": "9:16"},
            headers=headers,
        )
        assert generated.status_code == 201, show(generated)
        script = generated.json()
        assert len(script["scenes"]) >= 2
        # The mock is required to satisfy the same schema rule as the live model.
        assert (
            sum(s["duration_seconds"] for s in script["scenes"]) == script["total_duration_seconds"]
        )
        for scene in script["scenes"]:
            assert scene["video_prompt"], "every scene must carry a compiled prompt"

        after_script = await credits.get_balance(funded_user.id)
        assert after_script == starting_balance - script_cost

        scenes = list(
            await db.scalars(
                select(Scene)
                .where(Scene.project_id == uuid.UUID(project_id))
                .order_by(Scene.scene_number)
            )
        )
        assert len(scenes) == len(script["scenes"]), "scenes must be persisted, not just returned"

        # --- assets ----------------------------------------------------------
        planned = await client.post(f"{API}/projects/{project_id}/assets/plan", headers=headers)
        assert planned.status_code == 200, show(planned)
        pending = planned.json()["pending_assets"]
        assert pending > 0, "the script should request at least one reference image"

        # Planning must be idempotent: a second call cannot duplicate rows.
        replanned = await client.post(f"{API}/projects/{project_id}/assets/plan", headers=headers)
        assert replanned.status_code == 200, show(replanned)
        assert replanned.json()["pending_assets"] == pending

        asset_quote = await client.get(f"{API}/projects/{project_id}/assets/cost", headers=headers)
        assert asset_quote.status_code == 200, show(asset_quote)
        asset_cost = Decimal(str(asset_quote.json()["credits_required"]))

        made = await client.post(f"{API}/projects/{project_id}/assets/generate", headers=headers)
        assert made.status_code == 200, show(made)
        produced = [a for g in made.json()["scenes"] for a in g["assets"]]
        assert produced, "asset generation returned nothing"
        assert all(a["status"] == "generated" for a in produced), [a["status"] for a in produced]
        assert all(a["image_url"] for a in produced)

        after_assets = await credits.get_balance(funded_user.id)
        assert after_assets == after_script - asset_cost

        approved = await client.post(f"{API}/projects/{project_id}/assets/approve", headers=headers)
        assert approved.status_code == 200, show(approved)

        # Approval must attach the images as video references, or the whole
        # pre-generation step buys nothing.
        await db.refresh(scenes[0])
        with_refs = [s for s in scenes if s.reference_image_urls]
        assert with_refs, "approved assets were not attached to any scene"

        # --- video -----------------------------------------------------------
        model = await cheapest_enabled_model(db)
        started = await client.post(
            f"{API}/projects/{project_id}/generation",
            json={"model_slug": model.slug},
            headers=headers,
        )
        assert started.status_code == 202, show(started)
        assert started.json()["selected_model_slug"] == model.slug

        after_video_charge = await credits.get_balance(funded_user.id)
        assert after_video_charge < after_assets, "video generation must charge"

        # Poll exactly as the frontend does. The mock reports queued, then
        # running, then completed, so this loop has to run more than once.
        observed: set[str] = set()
        final = None
        for _ in range(12):
            polled = await client.get(f"{API}/projects/{project_id}/generation", headers=headers)
            assert polled.status_code == 200, show(polled)
            final = polled.json()
            statuses = {s["generation_status"] for s in final["scenes"]}
            observed |= statuses
            if statuses == {"completed"}:
                break

        assert final is not None
        assert {s["generation_status"] for s in final["scenes"]} == {"completed"}, observed
        assert "generating" in observed, (
            f"never observed an in-flight state, so the polling loop was "
            f"short-circuited: {observed}"
        )
        assert all(s["video_url"] for s in final["scenes"])

        # --- stitch ----------------------------------------------------------
        # This is the body of the `video.stitch_project` Celery task, driven
        # directly so the test does not need a broker or a worker.
        project = await db.scalar(select(Project).where(Project.id == uuid.UUID(project_id)))
        final_key = await StitchService(db, get_storage_adapter()).stitch_project(project)
        assert final_key, "stitching produced no key"
        await db.refresh(project)
        assert project.final_video_url == final_key

        # --- exports ---------------------------------------------------------
        treatment = await client.get(
            f"{API}/projects/{project_id}/export/treatment", headers=headers
        )
        assert treatment.status_code == 200, show(treatment)
        assert "Northwind Coffee" in treatment.text

        shot_list = await client.get(
            f"{API}/projects/{project_id}/export/shot-list", headers=headers
        )
        assert shot_list.status_code == 200, show(shot_list)
        assert shot_list.text.count("\n") >= len(script["scenes"])

        prompts = await client.get(f"{API}/projects/{project_id}/export/prompts", headers=headers)
        assert prompts.status_code == 200, show(prompts)

        video_url = await client.get(f"{API}/projects/{project_id}/export/video", headers=headers)
        assert video_url.status_code == 200, show(video_url)
        assert video_url.json()["url"]

        # --- accounting ------------------------------------------------------
        # Every debit is recorded, and the wallet agrees with the ledger.
        ledger_total = sum(
            Decimal(str(row.amount))
            for row in await db.scalars(
                select(CreditTransaction).where(CreditTransaction.user_id == funded_user.id)
            )
        )
        assert await credits.get_balance(funded_user.id) == ledger_total


class TestFailurePath:
    async def test_failed_scene_is_refunded(self, client, db, funded_user):
        """A permanently failed scene must return its credits.

        Exercised by injecting the mock's failure token into a compiled prompt,
        which makes that provider job report FAILED on every poll.
        """
        mock_video.reset_jobs()
        headers = auth(funded_user)
        credits = CreditService(db)

        created = await client.post(
            f"{API}/projects", json={"title": "Refund path"}, headers=headers
        )
        assert created.status_code == 201, show(created)
        project_id = created.json()["id"]

        await client.patch(f"{API}/projects/{project_id}", json={"brief": BRIEF}, headers=headers)
        generated = await client.post(
            f"{API}/projects/{project_id}/script",
            json={"ad_category": "problem-agitation-solution", "aspect_ratio": "9:16"},
            headers=headers,
        )
        assert generated.status_code == 201, show(generated)

        scenes = list(
            await db.scalars(
                select(Scene)
                .where(Scene.project_id == uuid.UUID(project_id))
                .order_by(Scene.scene_number)
            )
        )
        # Doom the first scene only, so the partial-failure path is what runs.
        scenes[0].compiled_prompt = f"{mock_video.FAIL_TOKEN} {scenes[0].compiled_prompt or ''}"
        await db.commit()

        model = await cheapest_enabled_model(db)
        before = await credits.get_balance(funded_user.id)
        started = await client.post(
            f"{API}/projects/{project_id}/generation",
            json={"model_slug": model.slug},
            headers=headers,
        )
        assert started.status_code == 202, show(started)
        charged = await credits.get_balance(funded_user.id)
        assert charged < before

        # MAX_ATTEMPTS is 3, so the scene needs several polls to fail for good.
        for _ in range(15):
            polled = await client.get(f"{API}/projects/{project_id}/generation", headers=headers)
            assert polled.status_code == 200, show(polled)
            statuses = {s["generation_status"] for s in polled.json()["scenes"]}
            if "failed" in statuses:
                break
            if not ({"pending", "generating"} & statuses):
                break

        after = await credits.get_balance(funded_user.id)
        assert after > charged, "a permanently failed scene was never refunded"
        # Only the doomed scene is refunded; the others stand.
        assert after < before, "the whole run was refunded, not just the failed scene"


class TestWorkerWiring:
    """The Celery task bodies are driven directly above; this covers registration.

    A task registered under the wrong name, or a module that fails to import,
    would leave the pipeline silently unable to progress in production.
    """

    async def test_tasks_are_registered_under_expected_names(self):
        from app.workers.celery_app import celery_app

        registered = set(celery_app.tasks.keys())
        for name in ("video.poll_project", "video.stitch_project", "video.retry_pending_scenes"):
            assert name in registered, sorted(n for n in registered if not n.startswith("celery."))
