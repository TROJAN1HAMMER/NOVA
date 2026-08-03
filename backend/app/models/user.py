"""
NOVA — User Model
Backs JWT authentication + RBAC + SSO. Scans can optionally be attributed
to an owner via `Scan.owner_id`.

A user is either "local" (password-authenticated, `hashed_password` set)
or provisioned by an SSO backend (`auth_provider` != LOCAL,
`hashed_password` left null, identified by `external_subject` — the
IdP's own unique identifier for this person: an OAuth2 `sub` claim, a
SAML NameID, or an LDAP DN, depending on `auth_provider`). Both kinds are
first-class rows in the same table rather than separate tables, since
everything downstream (role, permissions, scan ownership, audit log
`user_id`) treats them identically once authenticated — only the login
path differs.

A partial unique index on (auth_provider, external_subject) — unique only
where external_subject is not null, so any number of local users can
share a null external_subject — is created directly in the migration
(0006_rbac_sso_audit.py) rather than declared here, since SQLAlchemy's
declarative `Index(..., postgresql_where=...)` needs a real column
expression and this model's own `external_subject` isn't in scope yet at
class-body evaluation time.
"""

from typing import Optional

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AuthProvider, UserRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            # Persist `.value` ("read_only"), not `.name` ("READ_ONLY") —
            # the Postgres enum type created in the migration only permits
            # the lowercase value strings. See ScanJob.status for the same
            # pattern/gotcha.
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=UserRole.READ_ONLY,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(
            AuthProvider,
            name="auth_provider",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=AuthProvider.LOCAL,
    )
    # The IdP's own identifier for this identity (OAuth2 `sub`, SAML
    # NameID, LDAP DN) — null for local/password users.
    external_subject: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
