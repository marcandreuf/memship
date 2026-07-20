"""OAuth / OpenID Connect client registry.

Providers register lazily: a provider is only usable when its credentials are
configured, so a self-hosted install that never sets GOOGLE_CLIENT_ID simply
does not expose the Google routes.
"""

from authlib.integrations.starlette_client import OAuth

from app.core.config import settings

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"

oauth = OAuth()

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


def get_provider(name: str):
    """Return the registered client for ``name``, or None when not configured."""
    if name == "google" and not settings.google_sso_enabled:
        return None
    return getattr(oauth, name, None)


def provider_redirect_uri(name: str) -> str:
    """Callback URL registered with the provider console.

    Built from BACKEND_PUBLIC_URL because the provider redirects the browser
    straight back to the API, not to the frontend.
    """
    return f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/v1/auth/oauth/{name}/callback"