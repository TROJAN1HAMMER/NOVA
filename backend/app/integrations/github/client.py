"""
NOVA — GitHub Integration
Provides authenticated and public GitHub repository metadata lookups and archive downloads.
Supports personal access tokens (PAT) via server-side GITHUB_TOKEN configuration.
Enforces strict SSRF protection, redirect domain validation, and credential isolation.
"""

from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
import structlog

from app.config import get_settings
from app.core.exceptions import ValidationAppError
from app.integrations.base import RepoProvider

logger = structlog.get_logger(__name__)

BLOCKED_REDIRECT_PATTERNS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.",
    "10.",
    "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
    "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
]


class GitHubRepoProvider(RepoProvider):
    """
    Authenticated repository provider for GitHub.
    Allows downloading public repositories as well as authorized private repositories.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        if token is not None:
            self.token: Optional[str] = token.strip() or None
        else:
            settings_token = get_settings().github_token
            self.token = settings_token.strip() if (settings_token and settings_token.strip()) else None

    @property
    def is_authenticated(self) -> bool:
        """Indicates whether server-side GitHub credentials are configured."""
        return self.token is not None

    @staticmethod
    def validate_url_security(url: str) -> bool:
        """
        Validates a URL against SSRF, internal IPs, AWS metadata, credentials, and non-HTTPS.
        Returns True if safe and public HTTPS GitHub domain, False otherwise.
        """
        from app.services.security_intelligence.repository_ingestion import repository_ingestion_service
        try:
            repository_ingestion_service.validate_github_url(url)
            return True
        except Exception:
            return False

    @staticmethod
    def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
        parts = [p for p in urlparse(repo_url).path.split("/") if p]
        if len(parts) < 2:
            raise ValidationAppError(f"Could not parse owner/repo from GitHub URL: {repo_url}")
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo

    @staticmethod
    def _validate_redirect_url(redirect_url: str) -> None:
        """
        Validates that an archive redirect URL points strictly to trusted GitHub storage domains.
        Prevents SSRF, credential leakage to rogue hosts, and internal network pivot attacks.
        """
        if not redirect_url:
            raise ValidationAppError("Empty redirect URL received from GitHub.")

        try:
            parsed = urlparse(redirect_url)
        except Exception:
            raise ValidationAppError("Malformed redirect URL received from GitHub.")

        if parsed.scheme.lower() != "https":
            raise ValidationAppError("Insecure redirect scheme detected from GitHub.")

        netloc = parsed.netloc.lower()
        if "@" in netloc:
            raise ValidationAppError("Embedded credentials in redirect URL are prohibited.")

        if ":" in netloc:
            host, port = netloc.split(":", 1)
            if port != "443":
                raise ValidationAppError("Non-standard port in redirect URL is prohibited.")
        else:
            host = netloc

        for pattern in BLOCKED_REDIRECT_PATTERNS:
            if pattern in host:
                raise ValidationAppError("Redirect to private or internal network destination is prohibited.")

        is_allowed = (
            host == "codeload.github.com"
            or host == "github.com"
            or host.endswith(".github.com")
            or host.endswith(".githubusercontent.com")
            or host == "github-cloud.s3.amazonaws.com"
            or (host.endswith(".amazonaws.com") and "s3" in host)
        )
        if not is_allowed:
            raise ValidationAppError(f"Prohibited redirect target domain: {host}")

    async def get_repo_metadata(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Queries GitHub API for repository metadata.
        Determines existence, visibility, default branch, and access permissions.
        Differentiates authentication, authorization, rate limit, and existence errors.
        """
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "NOVA-Security-Intelligence",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(api_url, headers=headers)
            except httpx.RequestError as exc:
                logger.warning("github_integration.metadata_network_error", owner=owner, repo=repo, error=str(exc))
                raise ValidationAppError("Network error communicating with GitHub API.")

        if resp.status_code == 200:
            try:
                data = resp.json()
                return {
                    "exists": True,
                    "private": bool(data.get("private", False)),
                    "default_branch": data.get("default_branch") or "HEAD",
                    "name": data.get("name", repo),
                }
            except Exception:
                return {"exists": True, "private": False, "default_branch": "HEAD", "name": repo}

        elif resp.status_code == 401:
            raise ValidationAppError("Configured NOVA GitHub credential is invalid or expired.")

        elif resp.status_code == 403:
            remaining = resp.headers.get("x-ratelimit-remaining")
            if remaining == "0" or "rate limit" in resp.text.lower():
                raise ValidationAppError("GitHub API rate limit reached. Please try again later.")
            raise ValidationAppError("GitHub repository could not be accessed with the configured NOVA GitHub credentials.")

        elif resp.status_code == 404:
            if self.token:
                raise ValidationAppError("GitHub repository could not be accessed with the configured NOVA GitHub credentials.")
            raise ValidationAppError("This repository is private and NOVA does not have GitHub read access configured.")

        elif resp.status_code >= 500:
            raise ValidationAppError("GitHub service is currently unavailable. Please try again later.")

        else:
            raise ValidationAppError(f"GitHub API error (HTTP {resp.status_code}).")

    async def download_archive(
        self, repo_url: str, ref: Optional[str], *, dest_dir: Path
    ) -> Path:
        """
        Downloads the source archive for a repository via GitHub's API.
        If ref is not specified, uses the repository's discovered default branch.
        Safely follows storage redirects and strips the Authorization header on redirect.
        """
        owner, repo = self._parse_owner_repo(repo_url)

        meta = await self.get_repo_metadata(owner, repo)

        target_ref = (ref.strip() if ref and ref.strip() else meta.get("default_branch")) or "HEAD"

        dest_dir.mkdir(parents=True, exist_ok=True)
        archive_path = dest_dir / f"{owner}_{repo}_{target_ref}.tar.gz"

        archive_endpoint = f"https://api.github.com/repos/{owner}/{repo}/tarball/{target_ref}"
        api_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "NOVA-Security-Intelligence",
        }
        if self.token:
            api_headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(follow_redirects=False, timeout=120) as client:
            try:
                resp = await client.get(archive_endpoint, headers=api_headers)
            except httpx.RequestError as exc:
                raise ValidationAppError(f"Network error communicating with GitHub archive service: {str(exc)}")

            if resp.status_code in (301, 302, 307, 308):
                redirect_url = resp.headers.get("Location")
                if not redirect_url:
                    raise ValidationAppError("Missing redirect Location header in GitHub archive response.")

                self._validate_redirect_url(redirect_url)

                # STRIP Authorization header on redirect to external storage (S3 / codeload)
                # Pre-signed parameters in the redirect URL handle authentication.
                download_headers = {
                    "User-Agent": "NOVA-Security-Intelligence",
                }

                try:
                    async with client.stream("GET", redirect_url, headers=download_headers) as stream_resp:
                        if stream_resp.status_code != 200:
                            raise ValidationAppError(
                                f"Failed to download repository archive from storage (HTTP {stream_resp.status_code})."
                            )
                        with open(archive_path, "wb") as f:
                            async for chunk in stream_resp.aiter_bytes():
                                f.write(chunk)
                except httpx.RequestError as exc:
                    raise ValidationAppError(f"Network error downloading repository archive from storage: {str(exc)}")

            elif resp.status_code == 200:
                with open(archive_path, "wb") as f:
                    f.write(resp.content)

            elif resp.status_code == 404:
                raise ValidationAppError(f"Branch or reference '{target_ref}' not found in repository {owner}/{repo}.")

            elif resp.status_code == 401:
                raise ValidationAppError("Configured NOVA GitHub credential is invalid or expired.")

            elif resp.status_code == 403:
                remaining = resp.headers.get("x-ratelimit-remaining")
                if remaining == "0" or "rate limit" in resp.text.lower():
                    raise ValidationAppError("GitHub API rate limit reached. Please try again later.")
                raise ValidationAppError("GitHub repository could not be accessed with the configured NOVA GitHub credentials.")

            else:
                raise ValidationAppError(f"Failed to download archive from GitHub (HTTP {resp.status_code}).")

        file_size = archive_path.stat().st_size if archive_path.exists() else 0
        if file_size == 0:
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)
            raise ValidationAppError("Downloaded repository archive was empty.")

        logger.info(
            "github_integration.downloaded",
            owner=owner,
            repo=repo,
            ref=target_ref,
            path=str(archive_path),
            size_bytes=file_size,
        )
        return archive_path
