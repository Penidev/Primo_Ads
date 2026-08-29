"""Payment gateway adapter interface.

Every gateway must be able to (a) open a hosted checkout for a credit purchase
and (b) verify an inbound webhook. Verification is mandatory: credits are only
ever granted from a signature-verified server-side event (SECURITY.md §3).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckoutRequest:
    amount_usd: float
    description: str
    reference: str  # our internal purchase id (idempotency anchor)
    success_url: str
    cancel_url: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class CheckoutSession:
    gateway: str
    session_id: str
    checkout_url: str


@dataclass(frozen=True)
class WebhookEvent:
    """Normalised, verified gateway event."""

    gateway: str
    event_id: str  # used for idempotent processing
    event_type: str
    is_payment_success: bool
    amount_usd: float | None
    reference: str | None  # echo of CheckoutRequest.reference
    metadata: dict[str, str]


class PaymentError(Exception):
    """Gateway call failed. Message is safe to surface to the user."""


class WebhookVerificationError(Exception):
    """Signature/timestamp verification failed — the event must be discarded."""


class PaymentAdapter(ABC):
    gateway_name: str

    @abstractmethod
    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        """Open a hosted checkout session."""

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> WebhookEvent:
        """Verify the signature over the RAW body and return a normalised event.

        Must raise WebhookVerificationError on any mismatch. Implementations must
        use constant-time comparison and must not re-serialise the body.
        """
