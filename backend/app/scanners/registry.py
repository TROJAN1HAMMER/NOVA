"""
NOVA — Scanner Registry & Dispatcher
Central registry for all 9 security scanner adapters with parallel execution support.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import structlog

from app.scanners.ast_grep_scanner import AstGrepScanner
from app.scanners.base import BaseScanner
from app.scanners.docker_scanner import DockerScanner
from app.scanners.joern_scanner import JoernScanner
from app.scanners.nvd_scanner import NvdScanner
from app.scanners.osv_scanner import OsvScanner
from app.scanners.pip_audit_scanner import PipAuditScanner
from app.scanners.secrets_scanner import SecretsScanner
from app.scanners.semgrep_scanner import SemgrepScanner
from app.scanners.yaml_scanner import YamlScanner

logger = structlog.get_logger(__name__)

SCANNER_CLASSES: Dict[str, Type[BaseScanner]] = {
    "semgrep": SemgrepScanner,
    "ast-grep": AstGrepScanner,
    "joern": JoernScanner,
    "pip-audit": PipAuditScanner,
    "osv": OsvScanner,
    "nvd": NvdScanner,
    "secrets": SecretsScanner,
    "docker": DockerScanner,
    "yaml": YamlScanner,
}


def get_scanner(name: str) -> BaseScanner:
    """Instantiate and return a scanner adapter by its canonical name."""
    cls = SCANNER_CLASSES.get(name.lower())
    if not cls:
        raise ValueError(f"Unknown scanner: '{name}'. Supported scanners: {list(SCANNER_CLASSES.keys())}")
    return cls()


def get_all_scanners() -> List[BaseScanner]:
    """Return instantiated instances of all 9 registered scanners."""
    return [cls() for cls in SCANNER_CLASSES.values()]


async def run_all_scanners(
    target_path: Path | str,
    scanner_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Run specified or all scanners in parallel against target_path and collect standardized results."""
    target = Path(target_path)
    if not target.exists():
        logger.error("scanner.target_not_found", target=str(target))
        return []

    if scanner_names:
        scanners = [get_scanner(name) for name in scanner_names if name.lower() in SCANNER_CLASSES]
    else:
        scanners = get_all_scanners()

    tasks = [scanner.scan(target) for scanner in scanners]
    results: List[Dict[str, Any]] = await asyncio.gather(*tasks, return_exceptions=False)
    return results
