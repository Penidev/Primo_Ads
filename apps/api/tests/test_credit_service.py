"""Credit ledger tests — the money layer.

Requires the Postgres dev stack: `make test-api`.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import ActionPricing, CreditTransaction, PlatformSetting, VideoModel
from app.services.credit_service import (
    CREDIT_USD_RATIO_KEY,
    CreditService,
    InsufficientCreditsError,
    PricingNotConfiguredError,
)

pytestmark = pytest.mark.asyncio


# These helpers upsert rather than insert. CI runs the seed script before the
# suite, so baseline pricing rows and the credit ratio already exist; a plain
# insert hits the unique constraint. A seeded database is also the realistic
# condition, so tests should not depend on an empty one.


async def _pricing(db, action_key: str, credits: str) -> None:
    existing = await db.scalar(select(ActionPricing).where(ActionPricing.action_key == action_key))
    if existing is None:
        db.add(
            ActionPricing(
                action_key=action_key,
                display_name=action_key,
                base_credits=Decimal(credits),
                unit="per_generation",
                is_enabled=True,
            )
        )
    else:
        existing.base_credits = Decimal(credits)
        existing.is_enabled = True
    await db.flush()


async def _ratio(db, usd_per_credit: float | None) -> None:
    """Set the credit-to-USD ratio, or remove it entirely when None."""
    existing = await db.scalar(
        select(PlatformSetting).where(PlatformSetting.key == CREDIT_USD_RATIO_KEY)
    )
    if usd_per_credit is None:
        if existing is not None:
            await db.delete(existing)
    elif existing is None:
        db.add(
            PlatformSetting(
                key=CREDIT_USD_RATIO_KEY,
                value={"usd_per_credit": usd_per_credit},
            )
        )
    else:
        existing.value = {"usd_per_credit": usd_per_credit}
    await db.flush()


class TestPricing:
    async def test_action_cost_reads_from_database(self, db):
        await _pricing(db, "script_generation", "2")
        assert await CreditService(db).action_cost("script_generation") == Decimal("2")

    async def test_action_cost_scales_with_quantity(self, db):
        await _pricing(db, "asset_image", "0.5")
        cost = await CreditService(db).action_cost("asset_image", quantity=4)
        assert cost == Decimal("2.0")

    async def test_missing_pricing_fails_closed(self, db):
        with pytest.raises(PricingNotConfiguredError):
            await CreditService(db).action_cost("does_not_exist")

    async def test_disabled_pricing_fails_closed(self, db):
        db.add(
            ActionPricing(
                action_key="disabled_action",
                base_credits=Decimal("5"),
                is_enabled=False,
            )
        )
        await db.flush()
        with pytest.raises(PricingNotConfiguredError):
            await CreditService(db).action_cost("disabled_action")

    async def test_video_scene_cost_applies_model_multiplier(self, db):
        await _pricing(db, "video_scene", "5")
        db.add(
            VideoModel(
                slug="budget-model",
                display_name="Budget",
                provider="fal",
                credit_multiplier=Decimal("0.5"),
                is_enabled=True,
            )
        )
        await db.flush()
        # 5 base x 0.5 multiplier x 4 scenes = 10
        cost = await CreditService(db).video_scene_cost("budget-model", scene_count=4)
        assert cost == Decimal("10.0")

    async def test_disabled_model_is_rejected(self, db):
        await _pricing(db, "video_scene", "5")
        db.add(VideoModel(slug="off-model", credit_multiplier=Decimal("1"), is_enabled=False))
        await db.flush()
        with pytest.raises(PricingNotConfiguredError):
            await CreditService(db).video_scene_cost("off-model", scene_count=1)

    async def test_usd_ratio_defaults_when_unset(self, db):
        # The setting must be removed first. The seed writes 0.50, which happens
        # to equal DEFAULT_USD_PER_CREDIT, so without this the assertion would
        # pass while never exercising the fallback it claims to test.
        await _ratio(db, None)
        assert await CreditService(db).usd_per_credit() == Decimal("0.50")

    async def test_usd_ratio_reads_platform_setting(self, db):
        # Deliberately not 0.50, so this cannot pass on the default.
        await _ratio(db, 0.25)
        assert await CreditService(db).usd_per_credit() == Decimal("0.25")

    async def test_quote_usd_uses_ratio(self, db):
        await _ratio(db, 0.5)
        assert await CreditService(db).quote_usd(Decimal("30")) == Decimal("15.00")


class TestDeduction:
    async def test_deduct_reduces_balance_and_writes_ledger(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(seeded_user.id, Decimal("50"), transaction_type="purchase")

        new_balance = await service.deduct(
            seeded_user.id,
            Decimal("20"),
            transaction_type="script_generation",
        )

        assert new_balance == Decimal("30")
        assert await service.get_balance(seeded_user.id) == Decimal("30")

    async def test_every_change_has_a_ledger_row(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(seeded_user.id, Decimal("10"), transaction_type="purchase")
        await service.deduct(seeded_user.id, Decimal("4"), transaction_type="script_generation")

        count = await db.scalar(
            select(func.count())
            .select_from(CreditTransaction)
            .where(CreditTransaction.user_id == seeded_user.id)
        )
        assert count == 2

    async def test_ledger_records_balance_after(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(seeded_user.id, Decimal("10"), transaction_type="purchase")
        await service.deduct(seeded_user.id, Decimal("3"), transaction_type="script_generation")

        # Selected by transaction_type, not by position. Postgres `now()` is the
        # transaction timestamp, so rows written in one transaction share a
        # created_at and cannot be ordered by it.
        deduction = await db.scalar(
            select(CreditTransaction).where(
                CreditTransaction.user_id == seeded_user.id,
                CreditTransaction.transaction_type == "script_generation",
            )
        )
        assert Decimal(str(deduction.balance_after)) == Decimal("7")
        assert Decimal(str(deduction.amount)) == Decimal("-3")

    async def test_overspend_is_rejected(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(seeded_user.id, Decimal("5"), transaction_type="purchase")

        with pytest.raises(InsufficientCreditsError):
            await service.deduct(
                seeded_user.id, Decimal("10"), transaction_type="script_generation"
            )

    async def test_failed_deduction_leaves_balance_untouched(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(seeded_user.id, Decimal("5"), transaction_type="purchase")
        with pytest.raises(InsufficientCreditsError):
            await service.deduct(
                seeded_user.id, Decimal("99"), transaction_type="script_generation"
            )
        assert await service.get_balance(seeded_user.id) == Decimal("5")

    async def test_negative_amounts_rejected(self, db, seeded_user):
        with pytest.raises(ValueError):
            await CreditService(db).deduct(
                seeded_user.id, Decimal("-5"), transaction_type="script_generation"
            )


class TestRefund:
    async def test_refund_restores_credits(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(seeded_user.id, Decimal("20"), transaction_type="purchase")
        await service.deduct(seeded_user.id, Decimal("10"), transaction_type="video_generation")

        await service.refund(seeded_user.id, Decimal("10"), reference_type="scene")

        assert await service.get_balance(seeded_user.id) == Decimal("20")

    async def test_refund_is_recorded_as_its_own_entry(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(seeded_user.id, Decimal("10"), transaction_type="purchase")
        await service.refund(seeded_user.id, Decimal("5"))

        types = [
            row.transaction_type
            for row in await db.scalars(
                select(CreditTransaction).where(CreditTransaction.user_id == seeded_user.id)
            )
        ]
        assert "refund" in types


class TestGrant:
    async def test_purchase_updates_lifetime_purchased(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(
            seeded_user.id,
            Decimal("100"),
            transaction_type="purchase",
            count_as_purchase=True,
        )
        from app.models import Wallet

        wallet = await db.scalar(select(Wallet).where(Wallet.user_id == seeded_user.id))
        assert Decimal(str(wallet.lifetime_purchased)) == Decimal("100")

    async def test_non_purchase_grant_does_not_count_as_purchased(self, db, seeded_user):
        service = CreditService(db)
        await service.grant(seeded_user.id, Decimal("10"), transaction_type="admin_grant")
        from app.models import Wallet

        wallet = await db.scalar(select(Wallet).where(Wallet.user_id == seeded_user.id))
        assert Decimal(str(wallet.lifetime_purchased)) == Decimal("0")
