"""
NOVA — OAuth2/OIDC SSO Provider

Generic authorization-code-flow client — works against any standards-
compliant IdP (Okta, Auth0, Azure AD, Google, Keycloak, ...) since the 4
endpoint URLs and client credentials are all configuration, not
provider-specific code. Real, working code (unlike SAML — see
saml_provider.py) since this protocol is plain HTTP + JSON, nothing
requiring an XML/crypto toolkit.

CSRF protection: `state` is a random token stored in Redis with a short
TTL when the login redirect is issued, and consumed (checked + deleted)
exactly once on callback — a replayed or forged `state` fails closed.
"""

from typing import Optional
from urllib.parse import urlencode

import httpx
import redis.asyncio as redis
import structlog

from app.auth.sso.base import RedirectSSOProvider, SSOAuthError, SSOIdentity
from app.config import get_settings
from app.models.enums import AuthProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

STATE_TTL_SECONDS = 600  # 10 minutes — long enough for a real login, short enough to bound the replay window

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


class OAuth2Provider(RedirectSSOProvider):
    provider = AuthProvider.OAUTH2

    def is_configured(self) -> bool:
        return bool(
            settings.oauth2_enabled
            and settings.oauth2_client_id
            and settings.oauth2_authorize_url
            and settings.oauth2_token_url
            and settings.oauth2_userinfo_url
            and settings.oauth2_redirect_uri
        )

    async def get_login_redirect_url(self, *, state: str) -> str:
        await _get_redis().set(f"NOVA:sso:oauth2:state:{state}", "1", ex=STATE_TTL_SECONDS)
        params = {
            "response_type": "code",
            "client_id": settings.oauth2_client_id,
            "redirect_uri": settings.oauth2_redirect_uri,
            "scope": settings.oauth2_scope,
            "state": state,
        }
        return f"{settings.oauth2_authorize_url}?{urlencode(params)}"

    async def handle_callback(self, *, code: str, state: str) -> SSOIdentity:
        state_key = f"NOVA:sso:oauth2:state:{state}"
        r = _get_redis()
        seen = await r.get(state_key)
        if seen is None:
            raise SSOAuthError("Invalid or expired OAuth2 state — possible CSRF or a replayed callback")
        await r.delete(state_key)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                token_resp = await client.post(
                    settings.oauth2_token_url,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": settings.oauth2_redirect_uri,
                        "client_id": settings.oauth2_client_id,
                        "client_secret": settings.oauth2_client_secret,
                    },
                    headers={"Accept": "application/json"},
                )
                token_resp.raise_for_status()
                access_token = token_resp.json()["access_token"]
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                raise SSOAuthError(f"OAuth2 token exchange failed: {exc}") from exc

            try:
                userinfo_resp = await client.get(
                    settings.oauth2_userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                userinfo_resp.raise_for_status()
                userinfo = userinfo_resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise SSOAuthError(f"OAuth2 userinfo request failed: {exc}") from exc

        email = userinfo.get("email")
        subject = userinfo.get("sub")
        if not email or not subject:
            raise SSOAuthError("OAuth2 userinfo response is missing 'sub' and/or 'email'")

        return SSOIdentity(
            external_subject=str(subject),
            email=email,
            full_name=userinfo.get("name"),
            raw_attributes=userinfo,
        )


_oauth2_provider: Optional[OAuth2Provider] = None


def get_oauth2_provider() -> OAuth2Provider:
    global _oauth2_provider
    if _oauth2_provider is None:
        _oauth2_provider = OAuth2Provider()
    return _oauth2_provider
