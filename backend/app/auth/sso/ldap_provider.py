"""
NOVA — LDAP SSO Interface

Real "search+bind" authentication via `ldap3`: binds as a service account
(`ldap_bind_dn`/`ldap_bind_password`) to search the directory for the
user's DN by username, then re-binds as that DN with the user's own
password to verify it. This two-step pattern is standard practice because
most directories won't let a client bind directly with just a bare
username — you need the full DN, and a search is the only reliable way to
get it without every user needing to know their own DN.

`ldap3`'s API is synchronous (no native asyncio support) — run inside
`asyncio.to_thread`, the same offload pattern this codebase already uses
for reportlab PDF rendering and subprocess-based scanners.
"""

import asyncio
from typing import Optional

import structlog

from app.auth.sso.base import SSOAuthError, SSOIdentity
from app.config import get_settings
from app.models.enums import AuthProvider

logger = structlog.get_logger(__name__)
settings = get_settings()


class LDAPInterface:
    """
    The contract NOVA's LDAP integration is built against — a plain
    method contract rather than an ABC alongside the redirect-flow SSO
    providers (`RedirectSSOProvider`), since LDAP is a direct bind/search
    protocol, not a browser redirect: there's no login-redirect URL for
    it, just `authenticate(username, password)`.
    """

    provider = AuthProvider.LDAP

    def is_configured(self) -> bool:
        return bool(
            settings.ldap_enabled
            and settings.ldap_server_url
            and settings.ldap_bind_dn
            and settings.ldap_user_search_base
        )

    async def authenticate(self, *, username: str, password: str) -> SSOIdentity:
        if not self.is_configured():
            raise SSOAuthError(
                "LDAP is not configured — set LDAP_ENABLED=true and "
                "LDAP_SERVER_URL/LDAP_BIND_DN/LDAP_USER_SEARCH_BASE"
            )
        return await asyncio.to_thread(self._authenticate_sync, username, password)

    def _authenticate_sync(self, username: str, password: str) -> SSOIdentity:
        import ldap3
        from ldap3.core.exceptions import LDAPBindError, LDAPException
        from ldap3.utils.conv import escape_filter_chars

        server = ldap3.Server(settings.ldap_server_url, use_ssl=settings.ldap_use_ssl, get_info=ldap3.NONE)

        try:
            search_conn = ldap3.Connection(
                server, user=settings.ldap_bind_dn, password=settings.ldap_bind_password, auto_bind=True
            )
        except LDAPException as exc:
            raise SSOAuthError(f"LDAP service account bind failed: {exc}") from exc

        try:
            search_filter = settings.ldap_user_search_filter.format(username=escape_filter_chars(username))
            search_conn.search(
                settings.ldap_user_search_base,
                search_filter,
                attributes=[settings.ldap_email_attribute, settings.ldap_full_name_attribute],
            )
            entries = list(search_conn.entries)
        finally:
            search_conn.unbind()

        if not entries:
            raise SSOAuthError(f"No LDAP user found matching '{username}'")
        if len(entries) > 1:
            raise SSOAuthError(f"LDAP search for '{username}' matched more than one entry — ambiguous")

        entry = entries[0]
        user_dn = entry.entry_dn

        try:
            user_conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)
            user_conn.unbind()
        except LDAPBindError as exc:
            raise SSOAuthError("Invalid LDAP credentials") from exc
        except LDAPException as exc:
            raise SSOAuthError(f"LDAP authentication failed: {exc}") from exc

        email = str(entry[settings.ldap_email_attribute]) if settings.ldap_email_attribute in entry else None
        full_name = (
            str(entry[settings.ldap_full_name_attribute]) if settings.ldap_full_name_attribute in entry else None
        )
        if not email:
            raise SSOAuthError(f"LDAP entry for '{username}' has no '{settings.ldap_email_attribute}' attribute")

        return SSOIdentity(
            external_subject=user_dn,
            email=email,
            full_name=full_name,
            raw_attributes=dict(entry.entry_attributes_as_dict),
        )


_ldap_interface: Optional[LDAPInterface] = None


def get_ldap_interface() -> LDAPInterface:
    global _ldap_interface
    if _ldap_interface is None:
        _ldap_interface = LDAPInterface()
    return _ldap_interface
