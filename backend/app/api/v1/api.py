"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    activities,
    activity_modalities,
    activity_prices,
    auth,
    groups,
    health,
    members,
    membership_types,
    persons,
    registrations,
    settings,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(activities.router)
api_router.include_router(activity_modalities.router)
api_router.include_router(activity_prices.router)
api_router.include_router(groups.router)
api_router.include_router(members.router)
api_router.include_router(membership_types.router)
api_router.include_router(persons.router)
api_router.include_router(registrations.router)
api_router.include_router(settings.router)
