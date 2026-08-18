#!/usr/bin/env python3
"""Fail if a procedure names something that belongs to one project.

The whole point of this repo is the split: **steps** live here, **names** live in
the project's `docs/agent-overlay.yaml`. That split is easy to state and easy to
lose — the way it is lost is not a redesign, it is one convenient sentence
("run `uv run pytest`") added while fixing something else. A month later the
procedure only fits one repo again.

So the split is enforced mechanically rather than remembered. Every file under
`workflows/` and `references/` is scanned for tokens that can only be true of a
particular project, toolchain or forge. A file that legitimately contains them —
the per-forge dialects, the overlay documentation with its worked example —
declares itself exempt on its first line, in the open:

    <!-- unbound-check: exempt — documents the gh dialect -->

An exemption you can see in the file is a different thing from an exemption
buried in this script's allowlist, which is why there is no allowlist.

Usage::

    python scripts/check_unbound.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCANNED = ("workflows", "references")

EXEMPT = re.compile(r"<!--\s*unbound-check:\s*exempt")

# Each entry: (name, pattern, what to write instead).
RULES: tuple[tuple[str, str, str], ...] = (
    (
        "forge CLI",
        r"(?<![\w-])(gh|glab)\s+(issue|pr|label|repo|api|release)\b",
        "name the operation and let `references/forge-<kind>.md` supply the command",
    ),
    (
        "project or host name",
        r"(?i)\b(acme|example-app|examplecorp)\b",
        "say 'the project' / 'the deploy target' and read the name from the overlay",
    ),
    (
        "toolchain command",
        r"(?i)(uv run|\bpytest\b|\bruff\b|\balembic\b|\bnpx\b|\bnpm run\b|make map|make wrappers)",
        "read it from the overlay's `gate` or `docs_move_with_code`",
    ),
    (
        "project file",
        # `CODEMAP.md` is a project file; bare `codemap` is this contract's own
        # overlay key, and naming an overlay key is exactly what a procedure
        # should do. Match the file, not the key.
        r"(?i)(app/static|app\.css|AGENTS\.md|CODEMAP\.md|CHANGELOG\.md|uv\.lock|launch\.json|all_models)",
        "point at the overlay key that names the file (`conventions`, `codemap`, …)",
    ),
    (
        "project stack",
        r"(?i)\b(tailwind|jinja|fastapi|sqlalchemy|apscheduler|postgres|psql|docker)\b",
        "the stack is a project fact; describe the failure in stack-neutral terms",
    ),
    (
        "label name",
        r"(?i)(human-approved|design-needed|severity:|\bwip\b)",
        "use the overlay key (`issues.approved_label`, `issues.claim_label`, …)",
    ),
)

COMPILED = tuple((name, re.compile(pat), fix) for name, pat, fix in RULES)


def offences(path: Path) -> list[tuple[int, str, str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and EXEMPT.search(lines[0]):
        return []
    found = []
    for n, line in enumerate(lines, 1):
        for name, pattern, fix in COMPILED:
            if m := pattern.search(line):
                found.append((n, name, m.group(0), fix))
    return found


def self_test() -> int:
    """The guard is only worth its green runs if it can still go red.

    Exit-code-only ("the fixture failed") would keep passing after a rule was
    weakened, since the other five would still fire. So assert that **every**
    rule is tripped by the fixture written to trip it.
    """
    fixture = REPO / "tests" / "fixtures" / "bound"
    fired = {
        name
        for path in sorted((fixture / "workflows").rglob("*.md"))
        for _, name, _, _ in offences(path)
    }
    missing = sorted({name for name, _, _ in RULES} - fired)
    if missing:
        for name in missing:
            print(f"rule never fires on the fixture: {name}", file=sys.stderr)
        print(
            "\nThe guard cannot catch what it claims to. Either the rule was "
            "weakened, or the fixture stopped exercising it.",
            file=sys.stderr,
        )
        return 1
    print(f"guard can fail — all {len(fired)} rules tripped by the fixture")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="assert the bundled fixture still trips every rule, and exit",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=REPO,
        help="scan somewhere other than this repo (used to prove the guard can fail)",
    )
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    bad = 0
    scanned = 0
    for folder in SCANNED:
        folder_path = args.root / folder
        if not folder_path.is_dir():
            continue
        for path in sorted(folder_path.rglob("*.md")):
            scanned += 1
            for n, name, hit, fix in offences(path):
                bad += 1
                rel = path.relative_to(args.root)
                print(f"{rel}:{n}: {name} — {hit!r}", file=sys.stderr)
                print(f"    instead: {fix}", file=sys.stderr)
    if bad:
        print(
            f"\n{bad} project-bound reference(s) in procedures that are supposed to be "
            "repo-independent.\nEither move the name into the overlay, or mark the file "
            "exempt on line 1 with a reason.",
            file=sys.stderr,
        )
        return 1
    print(f"procedures are unbound ({scanned} files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
