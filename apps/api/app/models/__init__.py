"""SQLAlchemy ORM models.

Importing this package registers every model on the shared Base metadata so
Alembic autogenerate can discover them.
"""

from app.models.ad_blueprint import AdBlueprint
from app.models.audit import AuditLog, SecurityEvent
from app.models.credit import (
    ActionPricing,
    CreditPackage,
    CreditTransaction,
    SubscriptionPlan,
    Wallet,
)
from app.models.feature_flag import FeatureFlag
from app.models.generation_job import GenerationJob
from app.models.payment import CreditPurchase, ProcessedWebhook
from app.models.platform_setting import PlatformSetting
from app.models.project import Project
from app.models.scene import Scene, SceneAsset
from app.models.subscription import Subscription
from app.models.user import User
from app.models.video_model import VideoModel

__all__ = [
    "User",
    "Wallet",
    "CreditTransaction",
    "ActionPricing",
    "SubscriptionPlan",
    "CreditPackage",
    "Subscription",
    "Project",
    "Scene",
    "SceneAsset",
    "GenerationJob",
    "VideoModel",
    "AdBlueprint",
    "PlatformSetting",
    "FeatureFlag",
    "CreditPurchase",
    "ProcessedWebhook",
    "AuditLog",
    "SecurityEvent",
]
