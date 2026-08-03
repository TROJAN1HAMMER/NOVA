"""
NOVA — GitHub Integration
Downloads a repository archive via GitHub's codeload endpoint — no API
token required for public repos; pass one to the constructor for private
repos. Uses `httpx`, already a project dependency.
"""

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
import structlog

from app.core.exceptions import ValidationAppError
from app.integrations.base import RepoProvider

logger = structlog.get_logger(__name__)


class GitHubRepoProvider(RepoProvider):
    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token

    @staticmethod
    def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
        parts = [p for p in urlparse(repo_url).path.split("/") if p]
        if len(parts) < 2:
            raise ValidationAppError(f"Could not parse owner/repo from GitHub URL: {repo_url}")
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[: -len(".git")]
        return owner, repo

    async def download_archive(
        self, repo_url: str, ref: Optional[str], *, dest_dir: Path
    ) -> Path:
        owner, repo = self._parse_owner_repo(repo_url)
        ref = ref or "HEAD"
        download_url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{ref}"
        headers = {"Authorization": f"token {self.token}"} if self.token else {}

        dest_dir.mkdir(parents=True, exist_ok=True)
        archive_path = dest_dir / f"{owner}_{repo}_{ref}.tar.gz"

        async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
            async with client.stream("GET", download_url, headers=headers) as response:
                if response.status_code != 200:
                    raise ValidationAppError(
                        f"Failed to download {owner}/{repo}@{ref} from GitHub "
                        f"(HTTP {response.status_code})"
                    )
                with open(archive_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)

        logger.info(
            "github_integration.downloaded", owner=owner, repo=repo, ref=ref, path=str(archive_path)
        )
        return archive_path
