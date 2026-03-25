"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    activities,
    activity_attachments,
    activity_consents,
    activity_cover_image,
    activity_modalities,
    activity_prices,
    auth,
    contacts,
    discount_codes,
    groups,
    health,
    logo,
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
api_router.include_router(activity_attachments.router)
api_router.include_router(activity_attachments.upload_router)
api_router.include_router(activity_cover_image.router)
api_router.include_router(activity_consents.router)
api_router.include_router(activity_modalities.router)
api_router.include_router(activity_prices.router)
api_router.include_router(discount_codes.router)
api_router.include_router(discount_codes.validate_router)
api_router.include_router(groups.router)
api_router.include_router(members.router)
api_router.include_router(membership_types.router)
api_router.include_router(persons.router)
api_router.include_router(registrations.router)
api_router.include_router(settings.router)
api_router.include_router(logo.router)
api_router.include_router(contacts.router)
api_router.include_router(contacts.detail_router)
