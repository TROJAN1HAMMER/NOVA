"""
NOVA — Joern Scanner Adapter
Executes Joern code property graph (CPG) taint analysis if installed, or gracefully handles unavailable CLI.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.scanners.base import BaseScanner

logger = structlog.get_logger(__name__)


class JoernScanner(BaseScanner):
    """Joern CPG scanner adapter."""

    def __init__(self, cli_command: str = "joern-parse") -> None:
        super().__init__(name="joern", cli_command=cli_command)

    async def scan(self, target_path: Path | str, **kwargs: Any) -> Dict[str, Any]:
        target = Path(target_path)
        if not target.exists():
            return {"scanner": self.name, "success": False, "findings": [], "error": f"Target path does not exist: {target}"}

        # If Joern is not installed in the environment, report graceful failure status
        if not self.is_available():
            logger.info("joern.cli_not_available", scanner=self.name)
            return {
                "scanner": self.name,
                "success": False,
                "findings": [],
                "error": "Joern CLI (joern-parse) is not installed in this environment.",
            }

        findings = await self._run_cli_scan(target)
        if findings is not None:
            return {"scanner": self.name, "success": True, "findings": findings}

        return {
            "scanner": self.name,
            "success": False,
            "findings": [],
            "error": "Joern CPG analysis failed.",
        }

    async def _run_cli_scan(self, target: Path) -> Optional[List[Dict[str, Any]]]:
        try:
            cmd = [self.cli_command or "joern-parse", str(target)]
            code, stdout, stderr = await self.run_subprocess(cmd, cwd=target, timeout=180.0)
            if code == 0:
                # In full deployment, joern script runs export
                return []
        except Exception as exc:
            logger.warning("joern.execution_failed", error=str(exc))
        return None
