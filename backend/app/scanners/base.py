"""
NOVA — Base Scanner Adapter
Defines the base interface, common models, and utility helpers for all scanner adapters.
"""

import abc
import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)

# Common file extensions and ignore directories
IGNORED_DIRS: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
}


class BaseScanner(abc.ABC):
    """Abstract base class for all security scanner adapters."""

    def __init__(self, name: str, cli_command: Optional[str] = None) -> None:
        self.name = name
        self.cli_command = cli_command

    def is_available(self) -> bool:
        """Check if the external CLI binary for this scanner is installed and executable."""
        if not self.cli_command:
            return False
        return shutil.which(self.cli_command) is not None

    @abc.abstractmethod
    async def scan(self, target_path: Path | str, **kwargs: Any) -> Dict[str, Any]:
        """Execute a security scan on the target repository directory.

        Returns a dictionary conforming to the standard scanner result shape:
          {
            "scanner": str,
            "success": bool,
            "findings": List[Dict[str, Any]],
            "error": Optional[str]
          }
        """
        pass

    def walk_files(
        self,
        root_dir: Path | str,
        extensions: Optional[Set[str]] = None,
        include_filenames: Optional[Set[str]] = None,
    ) -> List[Path]:
        """Utility to safely walk files in the target directory, skipping ignored folders."""
        root = Path(root_dir)
        if not root.exists():
            return []

        matched_files: List[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Modify dirnames in-place to avoid descending into ignored directories.
            # Allow .github since workflow CI files live inside .github/workflows/
            dirnames[:] = [
                d for d in dirnames
                if d not in IGNORED_DIRS and (not d.startswith(".") or d == ".github")
            ]

            for fname in filenames:
                file_path = Path(dirpath) / fname
                ext = file_path.suffix.lower()
                name = file_path.name.lower()

                if include_filenames and name in include_filenames:
                    matched_files.append(file_path)
                elif extensions and ext in extensions:
                    matched_files.append(file_path)
                elif not extensions and not include_filenames:
                    matched_files.append(file_path)

        return matched_files

    def read_file_safe(self, file_path: Path | str) -> str:
        """Read a text file safely, ignoring decoding errors."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as exc:
            logger.debug("scanner.read_file_error", file=str(file_path), error=str(exc))
            return ""

    def relative_path_str(self, file_path: Path | str, root_dir: Path | str) -> str:
        """Return a POSIX-style relative path string from root_dir to file_path."""
        try:
            rel = Path(file_path).resolve().relative_to(Path(root_dir).resolve())
            return rel.as_posix()
        except Exception:
            return Path(file_path).as_posix()

    async def run_subprocess(
        self,
        args: List[str],
        cwd: Optional[Path | str] = None,
        timeout: float = 60.0,
    ) -> tuple[int, str, str]:
        """Run an external CLI command asynchronously with timeout protection."""
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="ignore")
            stderr = stderr_bytes.decode("utf-8", errors="ignore")
            return process.returncode or 0, stdout, stderr
        except asyncio.TimeoutError:
            logger.warning("scanner.cli_timeout", scanner=self.name, args=args)
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as exc:
            logger.warning("scanner.cli_execution_failed", scanner=self.name, error=str(exc))
            return -1, "", str(exc)
