"""
NOVA — Scan Orchestrator (RETIRED)
This module's sequential "run every scanner in one task" pipeline has
been replaced by a fan-out/fan-in design:

  - app/tasks/scan_tasks.py       — resolves the artifact once, extracts
                                     it, dispatches the chord
  - app/tasks/scanner_tasks.py    — the 9 independent, parallel scanner
                                     tasks (semgrep, ast-grep, joern,
                                     pip-audit, OSV, NVD, secrets, docker,
                                     yaml)
  - app/tasks/aggregator_tasks.py — the chord callback: merges results,
                                     scores, persists, finalizes the job

Nothing imports this module anymore (verified via repo-wide search)
except the already-stale standalone script `test_brs.py` at the repo
root, which predates the database-backed pipeline entirely and was never
updated to match it.
"""
