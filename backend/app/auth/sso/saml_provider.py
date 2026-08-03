"""
NOVA — SAML 2.0 SSO Provider (placeholder)

The config surface (`SAML_*` settings), the routes (`/auth/sso/saml/*`),
and this class's interface are all real and ready to wire up. What's
deliberately NOT implemented is SAML assertion parsing/signature
validation itself — that requires an XML security toolkit (e.g.
`python3-saml`, which wraps `xmlsec1`/`lxml` with native C bindings) that
isn't added as a dependency here. Hand-rolling XML signature verification
without a battle-tested library is a correctness and security trap (XML
canonicalization and signature-wrapping attacks are exactly the kind of
subtle bug class a security platform must not introduce casually), so
this stays an honest placeholder rather than a fragile partial
implementation.

To make this real:
  1. Add `python3-saml` (and its native `xmlsec1` system dependency) to
     the worker/API image.
  2. `get_login_redirect_url` builds and signs an `AuthnRequest`, deflate-
     encodes it, and redirects to the IdP's SSO URL with it as a query
     param (`python3-saml`'s `OneLogin_Saml2_Auth.login()` does this).
  3. `handle_callback` verifies the POSTed `SAMLResponse` (signature,
     conditions, audience, recipient) via
     `OneLogin_Saml2_Auth.process_response()`, then reads the validated
     NameID/attributes — never trust an unverified assertion's contents.
"""

from typing import Optional

from app.auth.sso.base import RedirectSSOProvider, SSOAuthError, SSOIdentity
from app.config import get_settings
from app.models.enums import AuthProvider

settings = get_settings()


class SAMLProvider(RedirectSSOProvider):
    provider = AuthProvider.SAML

    def is_configured(self) -> bool:
        # Even when "configured" (all settings present), this provider
        # can never actually complete a flow yet — see the module
        # docstring. is_configured() reflects "has the settings", not
        # "can be used", so config validation UI can show real feedback
        # without pretending logins would work.
        return bool(
            settings.saml_enabled
            and settings.saml_idp_metadata_url
            and settings.saml_idp_entity_id
            and settings.saml_acs_url
        )

    async def get_login_redirect_url(self, *, state: str) -> str:
        raise SSOAuthError(
            "SAML SSO is a placeholder in this deployment: the config/routes exist, "
            "but assertion validation requires adding python3-saml (see saml_provider.py docstring)."
        )

    async def handle_callback(self, **kwargs) -> SSOIdentity:
        raise SSOAuthError(
            "SAML SSO is a placeholder in this deployment: the config/routes exist, "
            "but assertion validation requires adding python3-saml (see saml_provider.py docstring)."
        )


_saml_provider: Optional[SAMLProvider] = None


def get_saml_provider() -> SAMLProvider:
    global _saml_provider
    if _saml_provider is None:
        _saml_provider = SAMLProvider()
    return _saml_provider
