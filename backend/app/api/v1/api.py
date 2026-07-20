"""API v1 router aggregation."""

from fastapi import APIRouter, Depends

from app.core.security.dependencies import require_approved_member
from app.api.v1.endpoints import (
    activities,
    activity_attachments,
    activity_consents,
    activity_cover_image,
    activity_modalities,
    activity_prices,
    auth,
    billing_runs,
    communications,
    concepts,
    contacts,
    discount_codes,
    groups,
    health,
    logo,
    mandates,
    member_card,
    member_photo,
    members,
    payment_providers,
    remittances,
    membership_types,
    persons,
    receipts,
    registrations,
    reminders,
    reports,
    settings,
    webhooks,
)

# Routers closed to members whose registration is still awaiting admin approval.
# Deliberately NOT applied to: auth (login/verify/resend/logout/me), settings
# (portal branding for the shell), members (its own guards; self-service profile
# must stay reachable so a pending applicant can review their data), health and
# webhooks (unauthenticated by design).
_approved_only = [Depends(require_approved_member)]

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(activities.router, dependencies=_approved_only)
api_router.include_router(activity_attachments.router, dependencies=_approved_only)
api_router.include_router(activity_attachments.upload_router, dependencies=_approved_only)
api_router.include_router(activity_cover_image.router, dependencies=_approved_only)
api_router.include_router(activity_consents.router, dependencies=_approved_only)
api_router.include_router(activity_modalities.router, dependencies=_approved_only)
api_router.include_router(activity_prices.router, dependencies=_approved_only)
api_router.include_router(discount_codes.router, dependencies=_approved_only)
api_router.include_router(discount_codes.validate_router, dependencies=_approved_only)
api_router.include_router(groups.router, dependencies=_approved_only)
api_router.include_router(members.router)
api_router.include_router(member_card.router, dependencies=_approved_only)
api_router.include_router(member_photo.router, dependencies=_approved_only)
api_router.include_router(membership_types.router, dependencies=_approved_only)
api_router.include_router(persons.router, dependencies=_approved_only)
api_router.include_router(registrations.router, dependencies=_approved_only)
api_router.include_router(reminders.router, dependencies=_approved_only)
api_router.include_router(reports.router, dependencies=_approved_only)
api_router.include_router(settings.router)
api_router.include_router(logo.router)
api_router.include_router(contacts.router, dependencies=_approved_only)
api_router.include_router(contacts.detail_router, dependencies=_approved_only)
api_router.include_router(contacts.types_router, dependencies=_approved_only)
api_router.include_router(payment_providers.router, dependencies=_approved_only)
api_router.include_router(mandates.member_router, dependencies=_approved_only)
api_router.include_router(mandates.router, dependencies=_approved_only)
api_router.include_router(remittances.router, dependencies=_approved_only)
api_router.include_router(receipts.member_router, dependencies=_approved_only)
api_router.include_router(receipts.router, dependencies=_approved_only)
api_router.include_router(concepts.router, dependencies=_approved_only)
api_router.include_router(billing_runs.router, dependencies=_approved_only)
api_router.include_router(communications.router, dependencies=_approved_only)
api_router.include_router(communications.me_router, dependencies=_approved_only)
api_router.include_router(webhooks.router)
