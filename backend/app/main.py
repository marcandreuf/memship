"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.uploads import router as uploads_router
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
# accept it with Secure. Since a provider can now be enabled at runtime from the
# settings screen (not only via env at boot), we can no longer key this off a
# specific provider's env creds. The oauth cookie is short-lived and its `state`
# param already guards CSRF, so using SameSite=None; Secure outside local dev is
# safe and lets Apple work once enabled in the UI. Local dev keeps the stricter
# Lax — Apple rejects localhost anyway, so it never needs the cross-site cookie.
_cross_site_oauth_cookie = settings.APP_ENV != "development"

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="memship_oauth",
    max_age=600,
    same_site="none" if _cross_site_oauth_cookie else "lax",
    https_only=_cross_site_oauth_cookie,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# Uploaded files. NOT a StaticFiles mount: the storage root also holds the
# encryption key, generated SEPA files and scanned mandates, and StaticFiles
# serves every one of them to anonymous callers. app/api/uploads.py enforces a
# per-prefix ownership rule and 404s anything without one.
storage_path = Path(settings.STORAGE_LOCAL_PATH)
storage_path.mkdir(parents=True, exist_ok=True)
app.include_router(uploads_router)
