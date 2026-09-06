"""
NOVA Security Intelligence — Utilities
Provides canonical path normalization, evidence sanitization, and repository path safety.
Strictly ensures no internal filesystem paths (e.g., /Users/..., /home/..., /tmp/..., scan UUID workspaces) escape to API or UI.
"""

import os
import re
from pathlib import Path
from typing import Optional, Union


# Patterns matching common workspace/temporary root directories
WORKSPACE_PREFIX_PATTERN = re.compile(
    r"^(?:(?:/[a-zA-Z0-9_.-]+)+/uploads/scans/[0-9a-fA-F-]+/source/[^/]+/|"
    r"(?:/[a-zA-Z0-9_.-]+)+/uploads/scans/[0-9a-fA-F-]+/source/|"
    r"(?:/[a-zA-Z0-9_.-]+)+/uploads/scans/[0-9a-fA-F-]+/|"
    r"/Users/[^/]+/(?:[^/]+/)*uploads/scans/[0-9a-fA-F-]+/source/[^/]+/|"
    r"/Users/[^/]+/(?:[^/]+/)*uploads/scans/[0-9a-fA-F-]+/source/|"
    r"/home/[^/]+/(?:[^/]+/)*uploads/scans/[0-9a-fA-F-]+/source/[^/]+/|"
    r"/tmp/(?:[^/]+/)*uploads/scans/[0-9a-fA-F-]+/source/[^/]+/|"
    r"/private/var/(?:[^/]+/)*uploads/scans/[0-9a-fA-F-]+/source/[^/]+/)",
    re.IGNORECASE,
)

SYSTEM_PREFIX_PATTERN = re.compile(
    r"^(?:/Users/[^/]+/|/home/[^/]+/|/tmp/|/private/var/|/var/)",
    re.IGNORECASE,
)


def normalize_repo_path(
    path: Union[str, Path, None],
    repo_root: Optional[Union[str, Path]] = None,
) -> str:
    """
    Converts any absolute local filesystem path or nested scan workspace path
    into a clean, repository-relative path (e.g. 'src/app.py', 'Backend/models/scaler.pkl').

    Guarantees:
    - Never leaks '/Users/...', '/home/...', '/tmp/...', or 'uploads/scans/...'.
    - Preserves line numbers or spans (e.g., 'src/app.py:42' or 'src/app.py:line 42').
    - Returns '.' if path refers to the repository root itself.
    """
    if not path:
        return "."

    path_str = str(path).strip().replace("\\", "/")

    # Extract any line number suffix if present (e.g., ':line 42', ':42', ':L42-50')
    line_suffix = ""
    line_match = re.search(r"(:line\s+\d+|:\d+(?:-\d+)?|:L\d+(?:-\d+)?)$", path_str, re.IGNORECASE)
    if line_match:
        line_suffix = line_match.group(1)
        path_str = path_str[: line_match.start()].strip()

    if not path_str or path_str in [".", "./"]:
        return f".{line_suffix}"

    # If repo_root is provided, try relative_to
    if repo_root:
        try:
            root_resolved = Path(repo_root).resolve()
            p_resolved = Path(path_str).resolve()
            if root_resolved == p_resolved:
                return f".{line_suffix}"
            rel = p_resolved.relative_to(root_resolved)
            rel_str = str(rel).replace("\\", "/")
            if rel_str in [".", "./"]:
                return f".{line_suffix}"
            return f"{rel_str}{line_suffix}"
        except Exception:
            pass

    # Strip scan workspace upload directory pattern
    if "uploads/scans/" in path_str:
        parts = path_str.split("uploads/scans/")
        if len(parts) > 1:
            rest = parts[1].strip("/")
            sub_parts = rest.split("/")
            # sub_parts: ['<uuid>', 'source', '<inner_folder>', '<rel_path>...']
            if len(sub_parts) >= 2 and sub_parts[1] == "source":
                if len(sub_parts) == 2:
                    return f".{line_suffix}"
                # If sub_parts[2] looks like a GitHub archive wrapper folder (e.g. owner-repo-sha7 or repo-branch)
                candidate_wrapper = sub_parts[2]
                is_github_wrapper = (
                    ("-" in candidate_wrapper and (len(candidate_wrapper.split("-")[-1]) >= 7 or candidate_wrapper.endswith(("-main", "-master", "-t1h"))))
                    or candidate_wrapper.startswith(("TROJAN1HAMMER-", "octocat-"))
                )
                if is_github_wrapper:
                    if len(sub_parts) == 3:
                        return f".{line_suffix}"
                    cleaned = "/".join(sub_parts[3:])
                else:
                    cleaned = "/".join(sub_parts[2:])
                return f"{cleaned or '.'}{line_suffix}"
            elif len(sub_parts) >= 1:
                if len(sub_parts) == 1:
                    return f".{line_suffix}"
                cleaned = "/".join(sub_parts[1:])
                return f"{cleaned or '.'}{line_suffix}"

    cleaned = WORKSPACE_PREFIX_PATTERN.sub("", path_str)
    if cleaned != path_str:
        cleaned = cleaned.lstrip("/")
        return f"{cleaned or '.'}{line_suffix}"

    # If still starts with system prefix, extract the trailing relative portion
    if SYSTEM_PREFIX_PATTERN.search(path_str):
        p = Path(path_str)
        parts = [part for part in p.parts if part not in ["/", "Users", "home", "tmp", "var", "private"]]
        if len(parts) > 1:
            if "source" in parts:
                idx = parts.index("source")
                # If ends at source or first dir under source, return '.'
                if idx == len(parts) - 1 or idx == len(parts) - 2:
                    return f".{line_suffix}"
                cleaned = "/".join(parts[idx + 2:])
            else:
                cleaned = "/".join(parts[-2:])
        else:
            cleaned = p.name
        cleaned = cleaned.lstrip("/")
        return f"{cleaned or '.'}{line_suffix}"

    # Strip leading slash or dot slash
    cleaned = path_str.lstrip("./").lstrip("/")
    return f"{cleaned or '.'}{line_suffix}"
