"""Aggregate router for all v1 endpoints.

Feature routers (auth, projects, scripts, billing, admin, ...) are registered
here as they are built in later phases.
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    assets,
    auth,
    billing,
    exports,
    generation,
    mfa,
    models,
    projects,
    scripts,
    swipe_file,
    users,
    webhooks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(mfa.router)
api_router.include_router(mfa.tos_router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(scripts.router)
api_router.include_router(assets.router)
api_router.include_router(models.router)
api_router.include_router(generation.router)
api_router.include_router(exports.router)
api_router.include_router(billing.router)
api_router.include_router(webhooks.router)
api_router.include_router(admin.router)
api_router.include_router(swipe_file.router)

# Admin routers are registered in the admin phase.
