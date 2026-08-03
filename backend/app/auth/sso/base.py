"""
NOVA — SSO Provider Interface

`SSOIdentity` is the normalized shape every SSO backend (OAuth2, SAML,
LDAP) resolves down to, regardless of how wildly different their wire
protocols are — a redirect-based authorization-code flow (OAuth2), an
XML assertion POSTed by a browser (SAML), or a directory bind/search
(LDAP). Everything past that point (find-or-create a `User`, issue
NOVA's own JWTs, audit-log the login) is identical for all three and
lives in the SSO router, not duplicated per provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.models.enums import AuthProvider


@dataclass
class SSOIdentity:
    external_subject: str
    email: str
    full_name: Optional[str] = None
    raw_attributes: Optional[dict] = None


class SSOAuthError(Exception):
    """Raised by any provider when the identity provider rejects the request or its response can't be trusted."""


class RedirectSSOProvider(ABC):
    """The shape shared by browser-redirect flows (OAuth2, SAML) — not LDAP, which is a direct bind, not a redirect."""

    provider: AuthProvider

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this provider has what it needs to be attempted at all."""

    @abstractmethod
    async def get_login_redirect_url(self, *, state: str) -> str:
        """Where to send the browser to start the flow."""

    @abstractmethod
    async def handle_callback(self, **kwargs) -> SSOIdentity:
        """
        Verifies the identity provider's response and returns a
        normalized identity. Raises SSOAuthError on anything that fails
        verification — an invalid state, a bad code exchange, an
        unparseable/unsigned assertion, etc. Keyword arguments are
        provider-specific (OAuth2: `code`; SAML: `saml_response`).
        """
