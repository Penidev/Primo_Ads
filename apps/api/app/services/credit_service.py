"""Credit wallet operations — the money layer.

Security-critical (SECURITY.md §3):
* Balances are only ever changed alongside an append-only ledger row.
* Every mutation takes a row-level lock (`SELECT ... FOR UPDATE`) so concurrent
  requests cannot double-spend (no check-then-act race).
* Prices are never hardcoded: they are read from `action_pricing`,
  `video_models.credit_multiplier`, and `platform_settings` at call time.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActionPricing, CreditTransaction, PlatformSetting, VideoModel, Wallet

CREDIT_USD_RATIO_KEY = "credit_usd_ratio"
DEFAULT_USD_PER_CREDIT = Decimal("0.50")


class InsufficientCreditsError(Exception):
    def __init__(self, required: Decimal, available: Decimal):
        self.required = required
        self.available = available
        super().__init__(f"Insufficient credits: need {required}, have {available}.")


class PricingNotConfiguredError(Exception):
    """Raised when an action has no pricing row — fail closed, never guess."""


class CreditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- pricing (all DB-driven) ----------

    async def usd_per_credit(self) -> Decimal:
        setting = await self.db.scalar(
            select(PlatformSetting).where(PlatformSetting.key == CREDIT_USD_RATIO_KEY)
        )
        if setting and isinstance(setting.value, dict):
            raw = setting.value.get("usd_per_credit")
            if raw is not None:
                return Decimal(str(raw))
        return DEFAULT_USD_PER_CREDIT

    async def action_cost(self, action_key: str, quantity: int = 1) -> Decimal:
        """Base credit cost for an action, multiplied by quantity."""
        pricing = await self.db.scalar(
            select(ActionPricing).where(ActionPricing.action_key == action_key)
        )
        if pricing is None or not pricing.is_enabled:
            raise PricingNotConfiguredError(f"No enabled pricing for action '{action_key}'.")
        return Decimal(str(pricing.base_credits)) * Decimal(quantity)

    async def video_scene_cost(
        self, model_slug: str, scene_count: int, action_key: str = "video_scene"
    ) -> Decimal:
        """Scene cost = action base credits x model multiplier x scene count."""
        base = await self.action_cost(action_key, quantity=1)
        model = await self.db.scalar(select(VideoModel).where(VideoModel.slug == model_slug))
        if model is None or not model.is_enabled:
            raise PricingNotConfiguredError(f"Video model '{model_slug}' unavailable.")
        multiplier = Decimal(str(model.credit_multiplier))
        return base * multiplier * Decimal(scene_count)

    async def quote_usd(self, credits: Decimal) -> Decimal:
        """Human-facing price estimate for a credit amount."""
        return (credits * await self.usd_per_credit()).quantize(Decimal("0.01"))

    # ---------- balance ----------

    async def get_balance(self, user_id: uuid.UUID) -> Decimal:
        wallet = await self.db.scalar(select(Wallet).where(Wallet.user_id == user_id))
        return Decimal(str(wallet.balance_credits)) if wallet else Decimal(0)

    async def _locked_wallet(self, user_id: uuid.UUID) -> Wallet:
        """Fetch the wallet with a row lock, creating it if missing."""
        wallet = await self.db.scalar(
            select(Wallet).where(Wallet.user_id == user_id).with_for_update()
        )
        if wallet is None:
            wallet = Wallet(user_id=user_id, balance_credits=0)
            self.db.add(wallet)
            await self.db.flush()
            wallet = await self.db.scalar(
                select(Wallet).where(Wallet.user_id == user_id).with_for_update()
            )
            assert wallet is not None  # noqa: S101 - invariant after insert
        return wallet

    # ---------- mutations ----------

    async def deduct(
        self,
        user_id: uuid.UUID,
        amount: Decimal,
        transaction_type: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        description: str | None = None,
    ) -> Decimal:
        """Atomically debit credits and append a ledger row. Returns new balance.

        The balance check and the debit happen inside one locked transaction so
        two concurrent generations cannot spend the same credits.
        """
        if amount < 0:
            raise ValueError("Deduction amount must be non-negative.")

        wallet = await self._locked_wallet(user_id)
        balance = Decimal(str(wallet.balance_credits))
        if balance < amount:
            raise InsufficientCreditsError(required=amount, available=balance)

        new_balance = balance - amount
        wallet.balance_credits = new_balance
        wallet.lifetime_spent = Decimal(str(wallet.lifetime_spent)) + amount

        self.db.add(
            CreditTransaction(
                user_id=user_id,
                amount=-amount,
                balance_after=new_balance,
                transaction_type=transaction_type,
                reference_type=reference_type,
                reference_id=reference_id,
                description=description,
            )
        )
        await self.db.commit()
        return new_balance

    async def grant(
        self,
        user_id: uuid.UUID,
        amount: Decimal,
        transaction_type: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        description: str | None = None,
        count_as_purchase: bool = False,
    ) -> Decimal:
        """Atomically credit the wallet and append a ledger row."""
        if amount < 0:
            raise ValueError("Grant amount must be non-negative.")

        wallet = await self._locked_wallet(user_id)
        balance = Decimal(str(wallet.balance_credits))
        new_balance = balance + amount
        wallet.balance_credits = new_balance
        if count_as_purchase:
            wallet.lifetime_purchased = Decimal(str(wallet.lifetime_purchased)) + amount

        self.db.add(
            CreditTransaction(
                user_id=user_id,
                amount=amount,
                balance_after=new_balance,
                transaction_type=transaction_type,
                reference_type=reference_type,
                reference_id=reference_id,
                description=description,
            )
        )
        await self.db.commit()
        return new_balance

    async def refund(
        self,
        user_id: uuid.UUID,
        amount: Decimal,
        reference_type: str | None = None,
        reference_id: str | None = None,
        description: str | None = None,
    ) -> Decimal:
        """Return credits after a failed generation (auto-refund path)."""
        return await self.grant(
            user_id,
            amount,
            transaction_type="refund",
            reference_type=reference_type,
            reference_id=reference_id,
            description=description or "Automatic refund for failed generation",
        )
