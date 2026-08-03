"""
NOVA — Local JSON Storage Engine
Replaces PostgreSQL with local file-based persistence for a zero-infrastructure prototype.
"""

import json
import os
import fcntl
from pathlib import Path
from contextlib import contextmanager

from app.config import get_settings

settings = get_settings()

DATA_DIR = Path(settings.data_dir)
SCANS_FILE = DATA_DIR / "scans.json"
FINDINGS_FILE = DATA_DIR / "findings.json"
REPORTS_FILE = DATA_DIR / "reports.json"


def init_store():
    """Ensure data directory and JSON files exist with empty lists/dicts."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    for file_path, default_data in [
        (SCANS_FILE, {}),     # Dict: {scan_id: scan_dict}
        (FINDINGS_FILE, {}),  # Dict: {scan_id: [finding_dicts]}
        (REPORTS_FILE, {}),   # Dict: {scan_id: [report_dicts]}
    ]:
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_data, f)


@contextmanager
def _locked_file(file_path: Path, mode: str = "r+"):
    """
    Context manager to acquire an exclusive lock on a file.
    Ensures safe concurrent reads/writes from background tasks and API requests.
    """
    # If mode is 'r+' and file doesn't exist, it will fail. init_store guarantees existence.
    with open(file_path, mode, encoding="utf-8") as f:
        # Acquire an exclusive lock
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _read_json(file_path: Path) -> dict:
    with _locked_file(file_path, "r") as f:
        return json.load(f)


def _write_json(file_path: Path, data: dict):
    with _locked_file(file_path, "w") as f:
        json.dump(data, f, indent=2)


# ── Scan Operations ──────────────────────────────────────────────────────────

def save_scan(scan_data: dict):
    """Create or update a scan record."""
    # Support both scan_id and legacy id when saving
    if "id" in scan_data and "scan_id" not in scan_data:
        scan_data["scan_id"] = scan_data.pop("id")
    scan_id = str(scan_data["scan_id"])
    data = _read_json(SCANS_FILE)
    data[scan_id] = scan_data
    _write_json(SCANS_FILE, data)


from typing import Optional


def get_scan(scan_id: str) -> Optional[dict]:
    """Retrieve a scan by ID."""
    data = _read_json(SCANS_FILE)
    scan = data.get(str(scan_id))
    if scan:
        # Convert legacy id to scan_id during load
        if "id" in scan and "scan_id" not in scan:
            scan["scan_id"] = scan.pop("id")
    return scan


def get_all_scans() -> list[dict]:
    """Retrieve all scans."""
    data = _read_json(SCANS_FILE)
    scans = list(data.values())
    for scan in scans:
        # Convert legacy id to scan_id during load
        if "id" in scan and "scan_id" not in scan:
            scan["scan_id"] = scan.pop("id")
    return scans


# ── Findings Operations ──────────────────────────────────────────────────────

def save_findings(scan_id: str, findings: list[dict]):
    """Save a list of findings for a specific scan."""
    data = _read_json(FINDINGS_FILE)
    data[str(scan_id)] = findings
    _write_json(FINDINGS_FILE, data)


def get_findings(scan_id: str) -> list[dict]:
    """Retrieve all findings for a specific scan."""
    data = _read_json(FINDINGS_FILE)
    return data.get(str(scan_id), [])


# ── Report Operations ────────────────────────────────────────────────────────

def save_report(report_data: dict):
    """Save a generated report metadata for a scan."""
    scan_id = str(report_data["scan_id"])
    data = _read_json(REPORTS_FILE)
    
    if scan_id not in data:
        data[scan_id] = []
        
    data[scan_id].append(report_data)
    _write_json(REPORTS_FILE, data)


def get_reports(scan_id: str) -> list[dict]:
    """Retrieve all report metadata for a specific scan."""
    data = _read_json(REPORTS_FILE)
    return data.get(str(scan_id), [])

# Initialize store on import
init_store()
