"""
NOVA — SSO Routes
OAuth2 (real, generic authorization-code flow), LDAP (real, search+bind),
and SAML (placeholder — 503 until a real XML security toolkit is wired
in, see `sso/saml_provider.py`).

Every successful SSO login find-or-creates a `User` row and issues
NOVA's own JWT pair exactly like `POST /auth/login` does — downstream
of that point, an SSO-authenticated session is indistinguishable from a
local one (same tokens, same role/permission model, same audit trail).
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from app.auth.schemas import LDAPLoginRequest, TokenResponse
from app.auth.service import AuthService
from app.auth.sso.base import SSOAuthError, SSOIdentity
from app.auth.sso.ldap_provider import get_ldap_interface
from app.auth.sso.oauth2_provider import get_oauth2_provider
from app.auth.sso.saml_provider import get_saml_provider
from app.core.exceptions import ServiceUnavailableError, UnauthorizedError
from app.models.enums import AuthProvider
from app.repositories.deps import get_user_repository
from app.repositories.user_repository import UserRepository
from app.services.audit.audit_logger import log_action

router = APIRouter()


async def _find_or_create_sso_user(users: UserRepository, identity: SSOIdentity, auth_provider: AuthProvider):
    user = await users.get_by_external_subject(auth_provider, identity.external_subject)
    if user is not None:
        return user
    # Deliberately does not attempt to link to an existing same-email
    # local account — silently merging identities by email is itself a
    # security decision (a compromised or misconfigured IdP could assert
    # any email), best made explicitly by an admin via the user-management
    # endpoints rather than automatically here.
    #
    # Commits immediately after creating a brand-new SSO user, before the
    # caller's subsequent `log_action(action="login", ...)` — that call
    # writes through audit_logger's own independent DB connection, which
    # can't see this row's FK target until it's committed (same fix, same
    # reasoning, as AuthService.register(); see its comment for the full
    # explanation, confirmed against a real Postgres instance).
    new_user = await users.create_sso_user(
        email=identity.email,
        full_name=identity.full_name,
        auth_provider=auth_provider,
        external_subject=identity.external_subject,
    )
    await users.db.commit()
    return new_user


@router.get("/auth/sso/oauth2/login")
async def oauth2_login():
    provider = get_oauth2_provider()
    if not provider.is_configured():
        raise ServiceUnavailableError("OAuth2 SSO is not configured (OAUTH2_ENABLED/OAUTH2_CLIENT_ID/...)")
    state = secrets.token_urlsafe(32)
    redirect_url = await provider.get_login_redirect_url(state=state)
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/auth/sso/oauth2/callback", response_model=TokenResponse)
async def oauth2_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    users: Annotated[UserRepository, Depends(get_user_repository)],
):
    provider = get_oauth2_provider()
    if not provider.is_configured():
        raise ServiceUnavailableError("OAuth2 SSO is not configured")

    try:
        identity = await provider.handle_callback(code=code, state=state)
    except SSOAuthError as exc:
        await log_action(
            action="login.failed", status="failure", request=request,
            details={"provider": "oauth2", "error": str(exc)},
        )
        raise UnauthorizedError(str(exc)) from exc

    user = await _find_or_create_sso_user(users, identity, AuthProvider.OAUTH2)
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    await log_action(
        user=user, action="login", resource_type="user", resource_id=str(user.id),
        request=request, details={"provider": "oauth2"},
    )
    return AuthService(users).issue_tokens(user)


@router.get("/auth/sso/saml/login")
async def saml_login():
    provider = get_saml_provider()
    if not provider.is_configured():
        raise ServiceUnavailableError("SAML SSO is not configured")
    raise ServiceUnavailableError(
        "SAML SSO is a placeholder in this deployment — config/routes exist, "
        "assertion validation is not implemented (see app/auth/sso/saml_provider.py)"
    )


@router.post("/auth/sso/saml/acs")
async def saml_acs():
    raise ServiceUnavailableError(
        "SAML SSO is a placeholder in this deployment — config/routes exist, "
        "assertion validation is not implemented (see app/auth/sso/saml_provider.py)"
    )


@router.post("/auth/ldap/login", response_model=TokenResponse)
async def ldap_login(
    payload: LDAPLoginRequest,
    request: Request,
    users: Annotated[UserRepository, Depends(get_user_repository)],
):
    interface = get_ldap_interface()
    try:
        identity = await interface.authenticate(username=payload.username, password=payload.password)
    except SSOAuthError as exc:
        await log_action(
            action="login.failed", status="failure", request=request,
            details={"provider": "ldap", "error": str(exc)},
        )
        raise UnauthorizedError(str(exc)) from exc

    user = await _find_or_create_sso_user(users, identity, AuthProvider.LDAP)
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    await log_action(
        user=user, action="login", resource_type="user", resource_id=str(user.id),
        request=request, details={"provider": "ldap"},
    )
    return AuthService(users).issue_tokens(user)
