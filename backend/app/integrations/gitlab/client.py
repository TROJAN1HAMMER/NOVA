"""
NOVA — GitLab Integration
Downloads a repository archive via GitLab's archive endpoint. Pass a
`PRIVATE-TOKEN` for private projects; public projects need none.
"""

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
import structlog

from app.core.exceptions import ValidationAppError
from app.integrations.base import RepoProvider

logger = structlog.get_logger(__name__)


class GitLabRepoProvider(RepoProvider):
    def __init__(self, token: Optional[str] = None, *, base_url: str = "https://gitlab.com") -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def _parse_project_path(repo_url: str) -> str:
        path = urlparse(repo_url).path.strip("/")
        if not path:
            raise ValidationAppError(f"Could not parse project path from GitLab URL: {repo_url}")
        if path.endswith(".git"):
            path = path[: -len(".git")]
        return path

    async def download_archive(
        self, repo_url: str, ref: Optional[str], *, dest_dir: Path
    ) -> Path:
        project_path = self._parse_project_path(repo_url)
        ref = ref or "HEAD"
        project_slug = project_path.rsplit("/", 1)[-1]
        download_url = f"{self.base_url}/{project_path}/-/archive/{ref}/{project_slug}-{ref}.tar.gz"
        headers = {"PRIVATE-TOKEN": self.token} if self.token else {}

        dest_dir.mkdir(parents=True, exist_ok=True)
        archive_path = dest_dir / f"{project_slug}_{ref}.tar.gz"

        async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
            async with client.stream("GET", download_url, headers=headers) as response:
                if response.status_code != 200:
                    raise ValidationAppError(
                        f"Failed to download {project_path}@{ref} from GitLab "
                        f"(HTTP {response.status_code})"
                    )
                with open(archive_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)

        logger.info(
            "gitlab_integration.downloaded", project=project_path, ref=ref, path=str(archive_path)
        )
        return archive_path
