"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(
    title="Memship API",
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/api/redoc" if settings.APP_ENV == "development" else None,
)

# Carries the OAuth `state`/`nonce` between the redirect out to the provider and
# the callback. It is short-lived and only written during an SSO handshake — the
# authenticated session itself remains the separate `access_token` JWT cookie.
#
# Apple returns the callback as a cross-site POST (response_mode=form_post), and
# browsers do not send SameSite=Lax cookies on those — the state would be missing
# and every Apple sign-in would fail. SameSite=None fixes it but browsers only
# accept it with Secure, which is fine because Apple requires an HTTPS redirect
# URI anyway (it rejects localhost). Google works either way, so the stricter Lax
# stays the default whenever Apple is not configured.
_apple_needs_cross_site_cookie = settings.apple_sso_enabled

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="memship_oauth",
    max_age=600,
    same_site="none" if _apple_needs_cross_site_cookie else "lax",
    https_only=_apple_needs_cross_site_cookie,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# Serve uploaded files (cover images, attachments)
storage_path = Path(settings.STORAGE_LOCAL_PATH)
storage_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(storage_path)), name="uploads")
