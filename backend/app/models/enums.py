"""
NOVA — Shared Model Enums
Plain `str` + `enum.Enum` so values serialize cleanly through Pydantic,
Celery's JSON task payloads, and Postgres's native ENUM type without any
custom encoder.
"""

import enum


class ScanJobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanJobPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RepoProviderType(str, enum.Enum):
    UPLOAD = "upload"
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class UserRole(str, enum.Enum):
    """
    The fixed RBAC role set — see app/auth/permissions.py for what each
    role can actually do (ROLE_PERMISSIONS). Not user-extensible: adding a
    role means adding an enum member + a migration, the same as any other
    enum in this file, rather than a dynamic Role table — there are 5 of
    these by design, not 5000.
    """

    ADMIN = "admin"
    AUDITOR = "auditor"
    DEVELOPER = "developer"
    SECURITY_ENGINEER = "security_engineer"
    READ_ONLY = "read_only"


class AuthProvider(str, enum.Enum):
    """How a user's identity was established — see app/auth/sso/."""

    LOCAL = "local"
    OAUTH2 = "oauth2"
    SAML = "saml"
    LDAP = "ldap"
