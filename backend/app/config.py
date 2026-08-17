"""
NOVA — Application Configuration
Reads all settings from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Annotated
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic import Field, field_validator
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "NOVA"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development", env="APP_ENV")
    app_secret_key: str = Field(default="change-me", env="APP_SECRET_KEY")
    debug: bool = Field(default=False, env="DEBUG")

    # Directories
    upload_dir: str = Field(default="uploads", env="UPLOAD_DIR")
    reports_dir: str = Field(default="reports", env="REPORTS_DIR")
    data_dir: str = Field(default="data", env="DATA_DIR")

    # Knowledge Base (RAG Milestone 1 — see app/services/knowledge_base/).
    # Documents are stored on disk under this directory (mirroring
    # reports_dir's local-storage pattern); only extracted text/chunks/
    # embeddings are ever persisted to the database. `knowledge_embedding_*`
    # must match the model actually pre-downloaded in the Dockerfile —
    # changing the model name here without also rebuilding the image (and
    # re-indexing existing documents, since a different model's vectors
    # aren't comparable) will fail at first use.
    knowledge_base_dir: str = Field(default="data/knowledge_base", env="KNOWLEDGE_BASE_DIR")
    knowledge_embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", env="KNOWLEDGE_EMBEDDING_MODEL")
    knowledge_embedding_dim: int = Field(default=384, env="KNOWLEDGE_EMBEDDING_DIM")
    knowledge_embedding_cache_dir: str = Field(
        default="data/fastembed_cache", env="KNOWLEDGE_EMBEDDING_CACHE_DIR"
    )
    # Chunk size measured with the same 4-chars/token heuristic as
    # app/services/ai/token_estimator.py — not an exact tokenizer count,
    # consistent with how the rest of NOVA already budgets text.
    knowledge_chunk_size_tokens: int = Field(default=350, env="KNOWLEDGE_CHUNK_SIZE_TOKENS")
    knowledge_chunk_overlap_tokens: int = Field(default=50, env="KNOWLEDGE_CHUNK_OVERLAP_TOKENS")
    knowledge_max_upload_mb: int = Field(default=25, env="KNOWLEDGE_MAX_UPLOAD_MB")
    knowledge_search_default_top_k: int = Field(default=5, env="KNOWLEDGE_SEARCH_DEFAULT_TOP_K")

    # AI Assistant (RAG Milestone 2 — see app/services/assistant/). Retrieval
    # is two-stage: pull `assistant_retrieval_candidates` chunks by cosine
    # similarity (vector_store.similarity_search, unchanged from Milestone 1),
    # then rerank them with a local cross-encoder and keep only
    # `assistant_top_k` for the LLM prompt / citations. The reranker is a
    # second local ONNX model (same no-external-API-call reasoning as the
    # embedding model), pre-downloaded into `assistant_rerank_cache_dir` at
    # Docker build time.
    assistant_rerank_model: str = Field(default="Xenova/ms-marco-MiniLM-L-6-v2", env="ASSISTANT_RERANK_MODEL")
    assistant_rerank_cache_dir: str = Field(default="data/rerank_cache", env="ASSISTANT_RERANK_CACHE_DIR")
    assistant_retrieval_candidates: int = Field(default=20, env="ASSISTANT_RETRIEVAL_CANDIDATES")
    assistant_top_k: int = Field(default=5, env="ASSISTANT_TOP_K")
    # The gate for "Never answer from model memory if nothing relevant is
    # retrieved": confidence is the sigmoid-normalized cross-encoder score of
    # the best-matching chunk (see rerank_manager.normalize_confidence). Below
    # this threshold, the assistant returns the fixed "could not find
    # sufficient information" message and never calls the LLM at all — this
    # is a deterministic check, not left to the model's discretion.
    assistant_min_confidence: float = Field(default=0.5, env="ASSISTANT_MIN_CONFIDENCE")
    assistant_max_history_turns: int = Field(default=6, env="ASSISTANT_MAX_HISTORY_TURNS")
    assistant_max_tokens: int = Field(default=1024, env="ASSISTANT_MAX_TOKENS")
    assistant_temperature: float = Field(default=0.2, env="ASSISTANT_TEMPERATURE")

    # AI — LLM provider abstraction (see app/services/ai/gateway.py). Every
    # provider is optional; unconfigured ones are skipped by is_configured()
    # rather than attempted and failed.
    #
    # ai_mode is the primary switch (see gateway.py's _resolve_provider_order):
    #   "cloud"  — only claude/openai/gemini are ever attempted.
    #   "local"  — only ollama/vllm are ever attempted; no cloud fallback,
    #              even if cloud keys happen to be configured.
    #   "hybrid" (default) — local first, cloud as fallback: "if local
    #              available use local, otherwise cloud". A local provider
    #              counts as "available" only if it actually answers — an
    #              unreachable Ollama/vLLM server fails over to cloud rather
    #              than blocking on it, since the gateway tries providers in
    #              order and only advances past one on failure.
    #
    # ai_provider_priority is an advanced escape hatch: leave it as "auto"
    # (default) to derive the order from ai_mode, or set an explicit
    # comma-separated list (e.g. "vllm,ollama,claude") to override it
    # outright, bypassing ai_mode entirely.
    ai_mode: str = Field(default="local", env="AI_MODE")
    ai_provider_priority: str = Field(default="auto", env="AI_PROVIDER_PRIORITY")
    ai_cache_ttl_seconds: int = Field(default=86400, env="AI_CACHE_TTL_SECONDS")

    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", env="ANTHROPIC_MODEL")

    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")

    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")

    # Local/self-hosted — no API key, just a reachable endpoint. Off by
    # default in practice: is_configured() requires ollama_model/vllm_model
    # to be set, since an empty served-model name can't be requested.
    # Known-good tags/repos for the 4 models NOVA is validated against
    # (see app/services/ai/local_models.py) — any Ollama tag or
    # vLLM-servable HF repo works, these are just the ones with the most
    # testing:
    #   Ollama:  ollama_model = "llama3" | "mistral" | "phi3" | "mixtral"
    #   vLLM:    vllm_model   = "meta-llama/Meta-Llama-3-8B-Instruct" |
    #                           "mistralai/Mistral-7B-Instruct-v0.3" |
    #                           "microsoft/Phi-3-mini-4k-instruct" |
    #                           "mistralai/Mixtral-8x7B-Instruct-v0.1"
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="", env="OLLAMA_MODEL")

    vllm_base_url: str = Field(default="http://localhost:8000", env="VLLM_BASE_URL")
    vllm_model: str = Field(default="", env="VLLM_MODEL")


    # Report storage (see app/services/reports/storage.py). "local" (default)
    # keeps the current behavior — reports live under reports_dir on the
    # worker's own disk, nothing new to configure. "s3" uploads every
    # generated report to an S3-compatible bucket (real AWS S3, or MinIO —
    # MinIO speaks the same API, just point s3_endpoint_url at it) and
    # downloads are served via short-lived presigned URLs instead of
    # streaming the file through the API process.
    report_storage_backend: str = Field(default="local", env="REPORT_STORAGE_BACKEND")
    s3_endpoint_url: str = Field(default="", env="S3_ENDPOINT_URL")  # blank = real AWS; set for MinIO, e.g. http://localhost:9000
    s3_bucket: str = Field(default="NOVA-reports", env="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", env="S3_REGION")
    s3_access_key_id: str = Field(default="", env="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="", env="S3_SECRET_ACCESS_KEY")
    # MinIO (and some S3-compatible stores) require path-style bucket
    # addressing (http://host/bucket/key) instead of virtual-hosted-style
    # (http://bucket.host/key), which real AWS S3 doesn't need.
    s3_use_path_style: bool = Field(default=True, env="S3_USE_PATH_STYLE")
    s3_presigned_url_expiry_seconds: int = Field(default=3600, env="S3_PRESIGNED_URL_EXPIRY_SECONDS")

    # Exa Web Search
    exa_enabled: bool = Field(default=False, env="EXA_ENABLED")

    # NVD API
    nvd_enabled: bool = Field(default=False, env="NVD_ENABLED")

    # CORS
    # `NoDecode` is required, not cosmetic: pydantic-settings' default
    # env-var handling for any complex-typed field (list, dict, ...)
    # attempts to JSON-decode the raw string *before* any Pydantic-level
    # validator ever sees it — a field_validator alone can't intercept or
    # fix that, since by then pydantic-settings has already raised trying
    # to json.loads() a plain comma-separated string. NoDecode disables
    # that source-level auto-decoding so the validator below gets the raw
    # string and can parse it correctly. Confirmed broken without this:
    # it crashed Celery beat/worker container startup the first time
    # ALLOWED_ORIGINS was actually supplied via a real environment
    # variable (a Kubernetes ConfigMap) in the documented
    # comma-separated format (`.env.example`'s
    # `ALLOWED_ORIGINS=http://a,http://b`) instead of silently falling
    # back to the Python-side default list, which is all any earlier
    # local testing had ever exercised.
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="ALLOWED_ORIGINS",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)  # explicit JSON array still supported
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    # Database (SQLAlchemy 2 async engine + Alembic)
    database_url: str = Field(
        default="postgresql+asyncpg://NOVA:NOVA_secret@localhost:5432/NOVA_db",
        env="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, env="DATABASE_ECHO")

    # Redis / Celery
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    celery_broker_url: str = Field(default="", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="", env="CELERY_RESULT_BACKEND")

    # JWT Authentication
    jwt_secret_key: str = Field(default="change-me-jwt-32chars-minimum", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # SSO — OAuth2/OIDC (see app/auth/sso/oauth2_provider.py). Generic
    # authorization-code-flow client that works against any standards-
    # compliant IdP (Okta, Auth0, Azure AD, Google, Keycloak, ...) — point
    # the 4 URLs at your provider's discovery document values. Unconfigured
    # (blank client_id) means the /auth/sso/oauth2/* routes respond 503
    # rather than attempting a flow with empty credentials.
    oauth2_enabled: bool = Field(default=False, env="OAUTH2_ENABLED")
    oauth2_client_id: str = Field(default="", env="OAUTH2_CLIENT_ID")
    oauth2_client_secret: str = Field(default="", env="OAUTH2_CLIENT_SECRET")
    oauth2_authorize_url: str = Field(default="", env="OAUTH2_AUTHORIZE_URL")
    oauth2_token_url: str = Field(default="", env="OAUTH2_TOKEN_URL")
    oauth2_userinfo_url: str = Field(default="", env="OAUTH2_USERINFO_URL")
    oauth2_redirect_uri: str = Field(default="", env="OAUTH2_REDIRECT_URI")
    oauth2_scope: str = Field(default="openid email profile", env="OAUTH2_SCOPE")

    # SSO — LDAP (see app/auth/sso/ldap_provider.py). Real bind-based
    # authentication via `ldap3` — binds as ldap_bind_dn to search for the
    # user's DN, then re-binds as that DN with the user's own password to
    # verify it (the standard "search+bind" pattern; avoids requiring every
    # client to know their own DN).
    ldap_enabled: bool = Field(default=False, env="LDAP_ENABLED")
    ldap_server_url: str = Field(default="", env="LDAP_SERVER_URL")  # e.g. "ldap://localhost:389"
    ldap_bind_dn: str = Field(default="", env="LDAP_BIND_DN")
    ldap_bind_password: str = Field(default="", env="LDAP_BIND_PASSWORD")
    ldap_user_search_base: str = Field(default="", env="LDAP_USER_SEARCH_BASE")
    ldap_user_search_filter: str = Field(default="(uid={username})", env="LDAP_USER_SEARCH_FILTER")
    ldap_email_attribute: str = Field(default="mail", env="LDAP_EMAIL_ATTRIBUTE")
    ldap_full_name_attribute: str = Field(default="cn", env="LDAP_FULL_NAME_ATTRIBUTE")
    ldap_use_ssl: bool = Field(default=False, env="LDAP_USE_SSL")

    # SSO — SAML 2.0 (see app/auth/sso/saml_provider.py). Placeholder: the
    # config surface, routes, and interface are real and ready to wire up,
    # but signature/assertion validation itself isn't implemented — that
    # needs a SAML XML toolkit (e.g. python3-saml) with native xmlsec
    # bindings, deliberately not added as a dependency here. Until then,
    # /auth/sso/saml/* routes respond 503 regardless of these settings.
    saml_enabled: bool = Field(default=False, env="SAML_ENABLED")
    saml_idp_metadata_url: str = Field(default="", env="SAML_IDP_METADATA_URL")
    saml_idp_entity_id: str = Field(default="", env="SAML_IDP_ENTITY_ID")
    saml_sp_entity_id: str = Field(default="NOVA", env="SAML_SP_ENTITY_ID")
    saml_acs_url: str = Field(default="", env="SAML_ACS_URL")  # Assertion Consumer Service callback URL

    # Audit log retention — sweep_stalled_jobs-style periodic cleanup isn't
    # wired up automatically; this just bounds how far back
    # GET /auth/audit-log queries are allowed to look without an explicit
    # override, so a careless "since the beginning of time" query can't
    # accidentally full-scan a huge table.
    audit_log_default_lookback_days: int = Field(default=90, env="AUDIT_LOG_DEFAULT_LOOKBACK_DAYS")

    # Notifications (see app/services/notifications/) — fired when a knowledge
    # ingestion job completes, when a job fails, or when the health check
    # detects a stalled pipeline worker. Every channel is independently
    # optional: leaving a channel's URL/host blank skips that channel.
    notifications_enabled: bool = Field(default=False, env="NOTIFICATIONS_ENABLED")
    notify_min_severity: str = Field(default="HIGH", env="NOTIFY_MIN_SEVERITY")

    slack_webhook_url: str = Field(default="", env="SLACK_WEBHOOK_URL")

    email_smtp_host: str = Field(default="", env="EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(default=587, env="EMAIL_SMTP_PORT")
    email_smtp_username: str = Field(default="", env="EMAIL_SMTP_USERNAME")
    email_smtp_password: str = Field(default="", env="EMAIL_SMTP_PASSWORD")
    email_smtp_use_tls: bool = Field(default=True, env="EMAIL_SMTP_USE_TLS")
    email_from_address: str = Field(default="NOVA@example.com", env="EMAIL_FROM_ADDRESS")
    email_to_addresses: Annotated[list[str], NoDecode] = Field(default=[], env="EMAIL_TO_ADDRESSES")

    webhook_url: str = Field(default="", env="WEBHOOK_URL")
    # HMAC-SHA256-signs the payload (header X-NOVA-Signature) when set,
    # the same pattern GitHub/Stripe webhooks use — lets the receiver
    # verify a notification genuinely came from this NOVA instance
    # rather than trusting an unauthenticated POST to a public URL.
    webhook_secret: str = Field(default="", env="WEBHOOK_SECRET")

    # Inbound GitHub webhook — GitHub calling into NOVA on push events for
    # knowledge source sync. Verified via X-Hub-Signature-256 header.
    # Left blank, the endpoint refuses every delivery with 503.
    github_webhook_secret: str = Field(default="", env="GITHUB_WEBHOOK_SECRET")

    # Data lifecycle — how long completed/failed knowledge job artifacts are
    # kept before the nightly archive sweep reclaims disk space.
    # Knowledge job DB records are never deleted — only temporary chunk files
    # and rendered report artifacts are reclaimed after this window.
    archive_after_days: int = Field(default=90, env="ARCHIVE_AFTER_DAYS")

    @field_validator("email_to_addresses", mode="before")
    @classmethod
    def _parse_email_to_addresses(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [addr.strip() for addr in stripped.split(",") if addr.strip()]
        return value

    @property
    def resolved_celery_broker_url(self) -> str:
        """Falls back to redis_url so a single REDIS_URL is enough for local dev."""
        return self.celery_broker_url or self.redis_url

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    def ensure_dirs(self) -> None:
        """Create required directories if they do not exist."""
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.knowledge_base_dir, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — use this everywhere."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
