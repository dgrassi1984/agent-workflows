#!/usr/bin/env python3
"""Validate a project's `agent-overlay.yaml` against `overlay.schema.json`.

Run this when authoring or changing a project's overlay. It answers two
questions the workflows cannot answer for themselves:

* **Is every key one this contract defines?** A typo'd key is the worst failure
  mode here, because nothing breaks: the workflow falls back to the conservative
  default and quietly stops at a pull request, or quietly works no queue at all,
  and the only symptom is an agent being oddly timid.
* **Does the file agree with itself?** `ship.after_merge: true` with
  `enabled` not true would have land-prs hand off to a release that must
  stop.

It deliberately does **not** check that the paths named inside exist — those are
repo-local facts, and the project checks them in its own CI where the files are.

Usage::

    python scripts/check_overlay.py <path-to-overlay.yaml> [...]
    python scripts/check_overlay.py --discover ~/Development     # every repo under a tree
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "overlay.schema.json"
CANDIDATES = ("docs/agent-overlay.yaml", "agent-overlay.yaml")


def discover(root: Path) -> list[Path]:
    """Every overlay under a directory of checkouts, in the documented order."""
    found = []
    for repo in sorted(p for p in root.iterdir() if (p / ".git").exists()):
        for rel in CANDIDATES:
            if (repo / rel).is_file():
                found.append(repo / rel)
                break
    return found


def check(path: Path, validator: Draft202012Validator) -> int:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"{path}: not valid YAML — {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print(f"{path}: overlay must be a mapping", file=sys.stderr)
        return 1

    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    for err in errors:
        where = ".".join(str(p) for p in err.path) or "(root)"
        print(f"{path}: {where}: {err.message}", file=sys.stderr)
    if errors:
        return 1
    print(f"{path}: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--discover", type=Path, help="scan a directory of checkouts")
    args = ap.parse_args()

    paths = list(args.paths)
    if args.discover:
        paths += discover(args.discover)
    if not paths:
        print("nothing to check (pass a path or --discover)", file=sys.stderr)
        return 1

    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    return max(check(p, validator) for p in paths)


if __name__ == "__main__":
    raise SystemExit(main())
