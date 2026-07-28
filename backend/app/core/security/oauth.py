"""OAuth / OpenID Connect client construction.

Provider credentials are resolved per request from the database (with env-var
fallback) rather than read once at import, so the settings screen can enable or
change a provider without a redeploy. A client is built on demand from the
resolved config; a provider that is not *ready* (enabled + fully configured)
simply yields ``None`` and its routes 404.
"""

import time

import jwt
from authlib.integrations.starlette_client import OAuth

from app.core.config import settings
from app.domains.auth.sso_config import ResolvedProvider, ResolvedSso

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


def _apple_private_key_pem(provider: ResolvedProvider) -> str:
    """The .p8 key with any escaped newlines restored to real ones."""
    return provider.get("private_key").replace("\\n", "\n").strip()


def build_apple_client_secret(provider: ResolvedProvider) -> str:
    """Apple's 'client secret' is an ES256 JWT signed with the .p8 key.

    Unlike every other provider there is no static secret to store, so this is
    minted fresh for each handshake from the resolved Apple credentials.
    """
    now = int(time.time())
    return jwt.encode(
        {
            "iss": provider.get("team_id"),
            "iat": now,
            "exp": now + APPLE_SECRET_TTL_SECONDS,
            "aud": APPLE_AUDIENCE,
            "sub": provider.get("client_id"),
        },
        _apple_private_key_pem(provider),
        algorithm="ES256",
        headers={"kid": provider.get("key_id")},
    )


def get_provider(name: str, resolved: ResolvedSso):
    """Build the authlib client for ``name`` from resolved config, or None.

    A fresh registry is used per call so a credential change from the settings
    screen takes effect on the next request without a restart.
    """
    provider = resolved.provider(name)
    if provider is None or not provider.ready:
        return None

    oauth = OAuth()
    if name == "google":
        oauth.register(
            name="google",
            client_id=provider.get("client_id"),
            client_secret=provider.get("client_secret"),
            # Discovery gives authlib the JWKS + endpoints, so the id_token is
            # signature/issuer/audience validated for us rather than by hand.
            server_metadata_url=GOOGLE_METADATA_URL,
            client_kwargs={"scope": "openid email profile"},
        )
        return oauth.create_client("google")

    if name == "apple":
        oauth.register(
            name="apple",
            client_id=provider.get("client_id"),
            # Replaced with a freshly signed JWT below — Apple's secret is a
            # short-lived signed JWT, not a static value.
            client_secret="",
            server_metadata_url=APPLE_METADATA_URL,
            client_kwargs=APPLE_CLIENT_KWARGS,
        )
        client = oauth.create_client("apple")
        client.client_secret = build_apple_client_secret(provider)
        return client

    return None


def provider_redirect_uri(name: str) -> str:
    """Callback URL registered with the provider console.

    Built from BACKEND_PUBLIC_URL because the provider redirects the browser
    straight back to the API, not to the frontend.
    """
    return f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/v1/auth/oauth/{name}/callback"