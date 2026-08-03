#!/usr/bin/env python
"""
NOVA — OpenAPI Spec Export
Dumps the live FastAPI app's OpenAPI schema (app.openapi(), the same
document served at /openapi.json) to a static file, for committing to the
repo, publishing to a docs site, or feeding an API-client generator —
without needing a running server.

Usage:
    python scripts/generate_openapi.py                         # writes openapi.json
    python scripts/generate_openapi.py --format yaml           # writes openapi.yaml
    python scripts/generate_openapi.py --output docs/api.json  # custom path
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Export NOVA's OpenAPI schema to a file.")
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output", default=None, help="Output path (default: openapi.<format> in the repo root)")
    args = parser.parse_args()

    from app.main import app

    schema = app.openapi()

    output_path = Path(args.output) if args.output else Path(__file__).resolve().parent.parent / f"openapi.{args.format}"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "yaml":
        import yaml

        output_path.write_text(yaml.dump(schema, sort_keys=False), encoding="utf-8")
    else:
        output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    route_count = sum(len(methods) for methods in schema.get("paths", {}).values())
    print(f"Wrote {output_path} ({len(schema.get('paths', {}))} paths, {route_count} operations)")


if __name__ == "__main__":
    main()
