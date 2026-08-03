"""
NOVA — Remote Repository Provider Interface
Backs `POST /scan/repository`: given a repo URL (and optional branch/tag/
commit ref), download an archive to a local path so the scan pipeline can
run against it exactly as it does an uploaded/extracted zip. Called from
`app/tasks/scan_tasks.py`'s prepare step, on the worker — not from the API
request itself, so submitting a repo URL can "return the scan ID
immediately" without waiting on the download.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class RepoProvider(ABC):
    @abstractmethod
    async def download_archive(
        self, repo_url: str, ref: Optional[str], *, dest_dir: Path
    ) -> Path:
        """
        Download a source archive for `repo_url` (optionally at `ref`) into
        `dest_dir` and return the path to the downloaded archive file.
        """
        raise NotImplementedError
