"""
NOVA — Report Storage Backend

Two backends behind one interface, selected by `settings.report_storage_backend`:

  "local" (default) — reports stay on the worker's local disk under
      `settings.reports_dir`, exactly as before this module existed. Zero
      configuration required; this is what every existing deployment gets
      unless it opts in to S3.

  "s3"    — every generated report is uploaded to an S3-compatible bucket
      via boto3. MinIO is API-compatible with S3, so pointing
      `S3_ENDPOINT_URL` at a MinIO instance (with `S3_USE_PATH_STYLE=true`,
      MinIO's usual requirement) works identically to real AWS S3 — same
      code path, no MinIO-specific branch needed.

`upload_report(local_path, storage_key)` is the only thing callers need:
it either leaves the file where it is (local backend — returns the same
path) or uploads it and returns the object key (s3 backend). Reading it
back for a download is `get_download_reference(storage_key_or_path)`,
which returns either a local `Path` to stream directly, or a presigned URL
to redirect to — the API layer (`app/api/v1/endpoints/reports.py`) decides
what to do with whichever it gets back.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class DownloadReference:
    """Exactly one of `local_path` / `presigned_url` is set, matching the backend that produced it."""

    local_path: Optional[Path] = None
    presigned_url: Optional[str] = None


class ReportStorage:
    """Backend-selecting facade — construct once per process, same as the AI gateway/providers pattern."""

    def __init__(self) -> None:
        self.backend = settings.report_storage_backend.strip().lower()
        self._s3_client = None
        if self.backend == "s3":
            self._s3_client = _build_s3_client()

    def is_s3(self) -> bool:
        return self.backend == "s3"

    def upload_report(self, local_path: Path, storage_key: str) -> str:
        """
        Returns the storage_key to persist on the Report row. For the local
        backend this is just the file's own path (nothing to upload); the
        file already lives at `local_path` and stays there.
        """
        if not self.is_s3():
            return str(local_path)

        try:
            self._s3_client.upload_file(str(local_path), settings.s3_bucket, storage_key)
            logger.info("report_storage.s3_upload_ok", bucket=settings.s3_bucket, key=storage_key)
            return storage_key
        except Exception as exc:
            logger.error("report_storage.s3_upload_failed", bucket=settings.s3_bucket, key=storage_key, error=str(exc))
            raise

    def delete_report(self, storage_key: str) -> None:
        """
        Reclaim a single report artifact — used by the archive sweep
        (app/tasks/archive_tasks.py), never by the download/status paths.
        Idempotent: a file/object that's already gone is not an error,
        since a retried or double-run sweep must be safe to repeat.
        """
        if not self.is_s3():
            path = Path(storage_key)
            path.unlink(missing_ok=True)
            return

        try:
            self._s3_client.delete_object(Bucket=settings.s3_bucket, Key=storage_key)
        except Exception as exc:
            logger.error("report_storage.s3_delete_failed", bucket=settings.s3_bucket, key=storage_key, error=str(exc))
            raise

    def get_download_reference(self, storage_key: str) -> DownloadReference:
        if not self.is_s3():
            return DownloadReference(local_path=Path(storage_key))

        url = self._s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": storage_key},
            ExpiresIn=settings.s3_presigned_url_expiry_seconds,
        )
        return DownloadReference(presigned_url=url)


def _build_s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
        region_name=settings.s3_region,
        config=_boto_config(),
    )


def _boto_config():
    from botocore.config import Config

    return Config(s3={"addressing_style": "path" if settings.s3_use_path_style else "virtual"})


_storage: Optional[ReportStorage] = None


def get_storage() -> ReportStorage:
    global _storage
    if _storage is None:
        _storage = ReportStorage()
    return _storage
