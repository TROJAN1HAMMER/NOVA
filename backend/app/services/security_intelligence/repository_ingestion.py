"""
NOVA Security Intelligence — Repository Ingestion Service
Handles secure ingestion, validation, isolation, and file enumeration for GitHub repositories and ZIP uploads.
"""

import io
import os
import re
import shutil
import tarfile
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
import structlog

from app.core.exceptions import ValidationAppError
from app.integrations.github.client import GitHubRepoProvider

logger = structlog.get_logger(__name__)

# Security thresholds
MAX_ZIP_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_EXTRACTED_SIZE_BYTES = 250 * 1024 * 1024  # 250 MB
MAX_ZIP_FILES = 10_000
MAX_COMPRESSION_RATIO = 100

IGNORED_DIRS: Set[str] = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".tox",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".idea",
    ".vscode",
    "vendor",
    "target",
    "bin",
    "obj",
    "uploads",
    "reports",
    "report",
    "Format b",
    ".pytest_cache",
    ".mypy_cache",
}

BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".pdf", ".wasm", ".so", ".dylib", ".dll", ".exe", ".bin",
    ".pyc", ".pyo", ".pyd", ".class", ".zip", ".tar", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".wav"
}

GITHUB_URL_REGEX = re.compile(r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$")
BLOCKED_HOST_PATTERNS = ["localhost", "127.0.0.1", "0.0.0.0", "169.254.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31."]


class RepositoryIngestionService:
    """Provides validated and isolated repository ingestion for security scanning."""

    def __init__(self, base_workspace_dir: Optional[str] = None):
        self.base_workspace_dir = Path(base_workspace_dir or "uploads/scans").resolve()
        self.base_workspace_dir.mkdir(parents=True, exist_ok=True)

    def validate_github_url(self, repo_url: str) -> Tuple[str, str]:
        """
        Validates a GitHub repository URL against SSRF, injection, and invalid domain attacks.
        Returns (owner, repo_name).
        """
        if not repo_url or not isinstance(repo_url, str):
            raise ValidationAppError("GitHub repository URL must be a non-empty string.")

        url_str = repo_url.strip()

        # Reject shell metacharacters and suspicious control characters
        if any(c in url_str for c in [";", "&", "|", "`", "$", "<", ">", "\n", "\r", "\t", " ", "\\"]):
            raise ValidationAppError("Invalid characters in GitHub repository URL.")

        try:
            parsed = urlparse(url_str)
        except Exception:
            raise ValidationAppError("Malformed GitHub repository URL.")

        if parsed.scheme.lower() != "https":
            raise ValidationAppError("Only secure HTTPS GitHub URLs are supported (e.g. https://github.com/owner/repo).")

        netloc = parsed.netloc.lower()
        if "@" in netloc:
            raise ValidationAppError("Embedded credentials in repository URL are prohibited.")

        if ":" in netloc:
            host, port = netloc.split(":", 1)
            if port != "443":
                raise ValidationAppError("Non-standard ports are prohibited for GitHub URLs.")
        else:
            host = netloc

        if host != "github.com":
            raise ValidationAppError("Only repositories on 'github.com' are supported.")

        # SSRF / blocked host check
        for pattern in BLOCKED_HOST_PATTERNS:
            if pattern in host or pattern in parsed.path:
                raise ValidationAppError("Private or internal network destinations are prohibited.")

        match = GITHUB_URL_REGEX.match(url_str)
        if not match:
            raise ValidationAppError("Invalid GitHub repository format. Expected: https://github.com/owner/repository")

        owner, repo = match.group(1), match.group(2)
        if owner.startswith(".") or repo.startswith("."):
            raise ValidationAppError("Invalid owner or repository name.")

        return owner, repo

    async def ingest_github_repository(self, repo_url: str, scan_id: str, branch: Optional[str] = None) -> Path:
        """
        Downloads and safely unpacks a public or authorized private GitHub repository into an isolated scan workspace.
        """
        owner, repo = self.validate_github_url(repo_url)
        workspace = self.base_workspace_dir / scan_id
        workspace.mkdir(parents=True, exist_ok=True)
        dest_dir = workspace / "source"
        dest_dir.mkdir(parents=True, exist_ok=True)

        provider = GitHubRepoProvider()
        archive_path: Optional[Path] = None
        try:
            clean_branch = branch.strip() if branch and branch.strip() else None
            archive_path = await provider.download_archive(repo_url, ref=clean_branch, dest_dir=workspace / "downloads")
            # Extract tar.gz archive safely with decomp bomb & path traversal protections
            self._safe_extract_tar(archive_path, dest_dir)
            # Find root dir inside dest_dir if wrapped in single top-level folder
            final_root = self._normalize_workspace_root(dest_dir)
            return final_root
        finally:
            if archive_path and archive_path.exists():
                try:
                    archive_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def validate_and_extract_zip(self, zip_data: bytes, scan_id: str) -> Path:
        """
        Validates and safely extracts a repository ZIP archive into an isolated scan workspace.
        Protects against Zip Slip, zip bombs, symlink attacks, and corrupted files.
        """
        if not zip_data or len(zip_data) == 0:
            raise ValidationAppError("Uploaded ZIP file is empty.")

        if len(zip_data) > MAX_ZIP_SIZE_BYTES:
            raise ValidationAppError(f"ZIP file exceeds maximum allowed size of {MAX_ZIP_SIZE_BYTES // (1024 * 1024)} MB.")

        if not zip_data.startswith(b"PK"):
            raise ValidationAppError("File is not a valid ZIP archive.")

        workspace = self.base_workspace_dir / scan_id
        workspace.mkdir(parents=True, exist_ok=True)
        dest_dir = workspace / "source"
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            zip_file = zipfile.ZipFile(io.BytesIO(zip_data))
        except Exception as exc:
            raise ValidationAppError(f"Corrupted or invalid ZIP archive: {str(exc)}")

        total_extracted_size = 0
        total_files = 0
        resolved_dest = dest_dir.resolve()

        with zip_file:
            infolist = zip_file.infolist()
            if len(infolist) > MAX_ZIP_FILES:
                raise ValidationAppError(f"ZIP contains {len(infolist)} entries, exceeding maximum limit of {MAX_ZIP_FILES}.")

            for info in infolist:
                filename = info.filename
                # Zip Slip Protection: canonicalize and verify path stays within dest_dir
                target_path = (dest_dir / filename).resolve()
                try:
                    target_path.relative_to(resolved_dest)
                except ValueError:
                    raise ValidationAppError(f"Zip Slip path traversal attempt detected in entry: {filename}")

                if ".." in filename.split("/") or ".." in filename.split("\\"):
                    raise ValidationAppError(f"Illegal relative path traversal in ZIP entry: {filename}")

                # Check compressed vs uncompressed ratio
                if info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > MAX_COMPRESSION_RATIO and info.file_size > 10 * 1024 * 1024:
                        raise ValidationAppError("Suspicious compression ratio detected (potential Zip Bomb).")

                total_extracted_size += info.file_size
                if total_extracted_size > MAX_EXTRACTED_SIZE_BYTES:
                    raise ValidationAppError(f"Extracted content exceeds maximum limit of {MAX_EXTRACTED_SIZE_BYTES // (1024 * 1024)} MB.")

                total_files += 1

                # Extract safe entries only
                if info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zip_file.open(info) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)

        final_root = self._normalize_workspace_root(dest_dir)
        return final_root

    def _safe_extract_tar(self, archive_path: Path, dest_dir: Path) -> None:
        """Safely extracts a tar.gz archive preventing path traversal, symlink attacks, and tar bombs."""
        resolved_dest = dest_dir.resolve()
        total_extracted_size = 0
        total_files = 0

        try:
            with tarfile.open(archive_path, "r:*") as tar:
                for member in tar.getmembers():
                    target_path = (dest_dir / member.name).resolve()
                    try:
                        target_path.relative_to(resolved_dest)
                    except ValueError:
                        raise ValidationAppError(f"Path traversal detected in tar archive: {member.name}")

                    if ".." in member.name.split("/") or ".." in member.name.split("\\"):
                        raise ValidationAppError(f"Illegal relative path traversal in tar entry: {member.name}")

                    if member.issym() or member.islnk():
                        # Reject symlinks pointing outside target
                        link_target = (target_path.parent / member.linkname).resolve()
                        try:
                            link_target.relative_to(resolved_dest)
                        except ValueError:
                            continue  # Skip unsafe symlink

                    total_files += 1
                    if total_files > MAX_ZIP_FILES:
                        raise ValidationAppError(f"Archive contains {total_files} entries, exceeding maximum limit of {MAX_ZIP_FILES}.")

                    total_extracted_size += member.size
                    if total_extracted_size > MAX_EXTRACTED_SIZE_BYTES:
                        raise ValidationAppError(
                            f"Extracted content exceeds maximum limit of {MAX_EXTRACTED_SIZE_BYTES // (1024 * 1024)} MB."
                        )

                    tar.extract(member, dest_dir)
        except ValidationAppError:
            raise
        except Exception as exc:
            raise ValidationAppError(f"Corrupted or invalid archive file: {str(exc)}")

    def _normalize_workspace_root(self, dest_dir: Path) -> Path:
        """If dest_dir contains a single top-level directory (e.g. GitHub archive root), returns that inner directory."""
        items = [p for p in dest_dir.iterdir() if p.name not in [".DS_Store", "__MACOSX"]]
        if len(items) == 1 and items[0].is_dir():
            return items[0]
        return dest_dir

    def enumerate_repository_files(self, repo_path: Path) -> Dict[str, Any]:
        """
        Enumerates all files in the repository, detecting languages, frameworks, manifests, and file paths.
        """
        all_files: List[Path] = []
        languages: Dict[str, int] = {}
        manifests: List[str] = []
        entry_points: List[str] = []
        config_files: List[str] = []

        if not repo_path.exists():
            return {
                "total_files": 0,
                "files": [],
                "languages": {},
                "manifests": [],
                "entry_points": [],
                "config_files": [],
            }

        for root, dirs, files in os.walk(repo_path):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

            for file in files:
                if file.startswith(".") and file not in [".env.example", ".env.local"]:
                    continue

                full_path = Path(root) / file
                rel_path = full_path.relative_to(repo_path)
                rel_str = str(rel_path).replace("\\", "/")
                ext = full_path.suffix.lower()

                if ext in BINARY_EXTENSIONS:
                    continue

                all_files.append(full_path)

                # Language detection
                if ext == ".py":
                    languages["Python"] = languages.get("Python", 0) + 1
                elif ext in [".js", ".jsx", ".mjs", ".cjs"]:
                    languages["JavaScript"] = languages.get("JavaScript", 0) + 1
                elif ext in [".ts", ".tsx"]:
                    languages["TypeScript"] = languages.get("TypeScript", 0) + 1
                elif ext == ".java":
                    languages["Java"] = languages.get("Java", 0) + 1
                elif ext == ".go":
                    languages["Go"] = languages.get("Go", 0) + 1
                elif ext in [".yml", ".yaml"]:
                    languages["YAML"] = languages.get("YAML", 0) + 1
                elif ext == ".json":
                    languages["JSON"] = languages.get("JSON", 0) + 1

                # Manifests
                if file in ["requirements.txt", "pyproject.toml", "Pipfile", "package.json", "pom.xml", "build.gradle", "go.mod", "Cargo.toml"]:
                    manifests.append(rel_str)

                # Entry points
                if file in ["main.py", "app.py", "server.js", "index.js", "main.ts", "index.ts", "Application.java", "main.go"]:
                    entry_points.append(rel_str)

                # Config files
                if "config" in file.lower() or "settings" in file.lower() or file.endswith(".env.example") or file == "docker-compose.yml" or file.startswith("Dockerfile"):
                    config_files.append(rel_str)

        return {
            "total_files": len(all_files),
            "files": [str(p.relative_to(repo_path)).replace("\\", "/") for p in all_files],
            "file_paths": all_files,
            "languages": languages,
            "manifests": manifests,
            "entry_points": entry_points,
            "config_files": config_files,
        }

    def cleanup_workspace(self, scan_id: str) -> None:
        """Safely cleans up an isolated scan workspace."""
        workspace = self.base_workspace_dir / scan_id
        if workspace.exists() and workspace.is_dir():
            try:
                shutil.rmtree(workspace, ignore_errors=True)
                logger.info("repository_ingestion.workspace_cleaned", scan_id=scan_id)
            except Exception as exc:
                logger.warning("repository_ingestion.cleanup_failed", scan_id=scan_id, error=str(exc))


repository_ingestion_service = RepositoryIngestionService()
