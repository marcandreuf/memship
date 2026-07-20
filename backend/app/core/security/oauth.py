"""OAuth / OpenID Connect client registry.

Providers register lazily: a provider is only usable when its credentials are
configured, so a self-hosted install that never sets GOOGLE_CLIENT_ID simply
does not expose the Google routes.
"""

import time

import jwt
from authlib.integrations.starlette_client import OAuth

from app.core.config import settings

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
APPLE_METADATA_URL = "https://appleid.apple.com/.well-known/openid-configuration"
APPLE_AUDIENCE = "https://appleid.apple.com"
# Apple caps the client secret at 6 months. We mint one per handshake, so it only
# has to outlive a single token exchange.
APPLE_SECRET_TTL_SECONDS = 300

# `openid` is required, not decorative: authlib only generates a nonce — and
# therefore only parses the returned id_token into `userinfo` — when the scope
# asks for it. Without it every Apple sign-in yields an empty profile. Apple
# advertises openid in its discovery document. `name`/`email` are only returned
# with form_post, which is also what makes the callback a POST.
APPLE_CLIENT_KWARGS = {"scope": "openid name email", "response_mode": "form_post"}

oauth = OAuth()


def build_apple_client_secret() -> str:
    """Apple's 'client secret' is an ES256 JWT signed with the .p8 key.

    Unlike every other provider there is no static secret to store, so this is
    minted fresh for each handshake and assigned to the client just before use.
    """
    now = int(time.time())
    return jwt.encode(
        {
            "iss": settings.APPLE_TEAM_ID,
            "iat": now,
            "exp": now + APPLE_SECRET_TTL_SECONDS,
            "aud": APPLE_AUDIENCE,
            "sub": settings.APPLE_CLIENT_ID,
        },
        settings.apple_private_key_pem,
        algorithm="ES256",
        headers={"kid": settings.APPLE_KEY_ID},
    )

if settings.google_sso_enabled:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        # Discovery gives authlib the JWKS + endpoints, so the id_token is
        # signature/issuer/audience validated for us rather than by hand.
        server_metadata_url=GOOGLE_METADATA_URL,
        client_kwargs={"scope": "openid email profile"},
    )


if settings.apple_sso_enabled:
    oauth.register(
        name="apple",
        client_id=settings.APPLE_CLIENT_ID,
        # Replaced with a freshly signed JWT on every use — see get_provider.
        client_secret="",
        server_metadata_url=APPLE_METADATA_URL,
        client_kwargs=APPLE_CLIENT_KWARGS,
    )


def get_provider(name: str):
    """Return the registered client for ``name``, or None when not configured."""
    if name == "google" and not settings.google_sso_enabled:
        return None
    if name == "apple":
        if not settings.apple_sso_enabled:
            return None
        client = getattr(oauth, "apple", None)
        if client is not None:
            # Apple's secret is a short-lived signed JWT, so refresh it rather
            # than relying on whatever was minted at import time.
            client.client_secret = build_apple_client_secret()
        return client
    return getattr(oauth, name, None)


def provider_redirect_uri(name: str) -> str:
    """Callback URL registered with the provider console.

    Built from BACKEND_PUBLIC_URL because the provider redirects the browser
    straight back to the API, not to the frontend.
    """
    return f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/v1/auth/oauth/{name}/callback"