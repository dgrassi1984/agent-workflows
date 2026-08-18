#!/usr/bin/env python3
"""Bind a project checkout to the repo-independent workflows.

The procedures live once, in this repository. A project opts in by writing a
small overlay that supplies the *names* — which forge, which labels, which
command is the gate. This command walks those decisions interactively, writes
what you decide, and leaves a commented placeholder for every key you skip.

It never copies a procedure into the project. That is the failure this repo
exists to stop: five drifting procedures, each half-rewritten for one codebase.
It does write generated *pointers* into the project's harness skill
directories so a harness that scans the checkout can invoke them, and it
gitignores those files — they are regenerated, not owned by the project.

Usage, from the project you want to bind::

    python3 ~/Development/agent-workflows/scripts/setup_repo.py

Or from this repo::

    make setup-repo DIR=/path/to/project

On a TTY it interviews. `--non-interactive` (or a non-TTY) writes only what it
can see on disk and leaves placeholders for the rest. It will not invent a
gate or a release ritual. Branch prefixes are read from `origin`, not typed.
Issue labels you opt into (`human-approved`, `wip`, `design-needed`, a
severity scheme) are created on the forge if they are missing. A yes to the
code map writes `docs/CODEMAP.md` from tracked sources. Generated skill
wrappers land in the project's harness directories and are added to
`.gitignore`.

The overlay goes to `docs/agent-overlay.yaml` when `docs/` exists, otherwise
the repo root. It will not overwrite without `--force` (non-interactive) or an
explicit yes (interactive).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home()

CONVENTIONS_CANDIDATES = ("AGENTS.md", "CONTRIBUTING.md")
CODEMAP_CANDIDATES = ("docs/CODEMAP.md", "CODEMAP.md")
CLEAR = "-"

# Standard names this operator already uses across repos. The interview
# offers them as yes/no; setup creates any that the forge is missing.
DEFAULT_APPROVED = "human-approved"
DEFAULT_CLAIM = "wip"
DEFAULT_BLOCK = "design-needed"
SEVERITY_P0 = ["P0", "P1", "P2", "P3", "P4", "P5"]
SEVERITY_WORDS = [
    "severity:critical",
    "severity:high",
    "severity:medium",
    "severity:low",
]
# Remote-branch names that are not a prefix.
NOT_A_PREFIX = frozenset({"HEAD", "main", "master", "develop", "staging", "trunk"})

# (description, hex without #) for labels we create. Unknown names get a
# generic description and a reserved color rather than a random one.
LABEL_META: dict[str, tuple[str, str]] = {
    DEFAULT_APPROVED: ("Cleared to build. Agents never set this.", "0E8A16"),
    "approved": ("Cleared to build. Agents never set this.", "0E8A16"),
    DEFAULT_BLOCK: ("Blocked on a human product decision.", "D93F0B"),
    "blocked": ("Blocked on a human product decision.", "D93F0B"),
    DEFAULT_CLAIM: ("A session is working this issue.", "FBCA04"),
    "in-progress": ("A session is working this issue.", "FBCA04"),
    "P0": ("Highest severity.", "B60205"),
    "P1": ("High severity.", "D93F0B"),
    "P2": ("Medium severity.", "FBCA04"),
    "P3": ("Low severity.", "0E8A16"),
    "P4": ("Lower severity.", "1D76DB"),
    "P5": ("Lowest severity.", "5319E7"),
    "severity:critical": ("Highest severity.", "B60205"),
    "severity:high": ("High severity.", "D93F0B"),
    "severity:medium": ("Medium severity.", "FBCA04"),
    "severity:low": ("Low severity.", "0E8A16"),
}
GENERIC_LABEL = ("Used by the agent-workflows overlay.", "5319E7")


def profile_root() -> Path:
    """The primary checkout, even when this file is running from a worktree."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return REPO
    git_dir = Path(proc.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (REPO / git_dir).resolve()
    if git_dir.name == ".git":
        return git_dir.parent
    return REPO


def profile_label() -> str:
    """How this repo should be named in a comment an agent will read."""
    root = profile_root()
    try:
        return "~/" + str(root.relative_to(HOME))
    except ValueError:
        return str(root)


def yaml_str(value: str) -> str:
    """Quote a scalar only when YAML would otherwise misread it."""
    if value == "" or value != value.strip() or value in {
        "true", "false", "null", "yes", "no", "on", "off",
        "True", "False", "None", "Yes", "No",
    }:
        return json.dumps(value)
    if any(c in value for c in ":#{}[]&*!|>%@`'\"\n") or value[:1] in "-?":
        return json.dumps(value)
    return value


@dataclass
class Overlay:
    """One project's bindings. None / empty means 'leave a placeholder'."""

    name: str
    target: Path
    conventions: str | None = None
    codemap: str | None = None
    primary_checkout: str = "read-only"
    forge_kind: str | None = None
    forge_repo: str | None = None
    default_branch: str | None = None
    branch_prefixes: list[str] = field(default_factory=list)
    approved_label: str | None = None
    block_labels: list[str] = field(default_factory=list)
    claim_label: str | None = None
    severity_labels: list[str] = field(default_factory=list)
    gate: list[str] = field(default_factory=list)
    worktree_root: str | None = None
    worktree_provision: str | None = None
    ship_enabled: bool = False
    ship_authorization: str = "ask"
    ship_procedure: str | None = None
    failure_classes: str | None = None
    docs_move_with_code: list[str] = field(default_factory=list)
    install_codemap: bool = False

    def never_set(self) -> list[str]:
        """The labels/fields an agent must not touch, derived from what we set."""
        out = []
        if self.approved_label:
            out.append(self.approved_label)
        if self.claim_label:
            out.append(self.claim_label)
        out += ["assignee", "milestone"]
        return out

    def issue_labels(self) -> list[str]:
        """Every forge label this overlay will name, in a stable order."""
        names: list[str] = []
        for name in (
            self.approved_label,
            *self.block_labels,
            self.claim_label,
            *self.severity_labels,
        ):
            if name and name not in names:
                names.append(name)
        return names

    def decided(self) -> list[str]:
        found = [f"project.name={self.name}", f"primary_checkout={self.primary_checkout}"]
        if self.conventions:
            found.append(f"conventions={self.conventions}")
        if self.codemap:
            found.append(f"codemap={self.codemap}")
        if self.forge_kind and self.forge_repo:
            found.append(f"forge={self.forge_kind} {self.forge_repo}")
        if self.default_branch:
            found.append(f"default_branch={self.default_branch}")
        if self.branch_prefixes:
            found.append("branch_prefixes")
        if self.approved_label or self.block_labels or self.claim_label or self.severity_labels:
            found.append("issues")
        if self.gate:
            found.append("gate")
        if self.worktree_root or self.worktree_provision:
            found.append("worktree")
        if self.ship_enabled:
            found.append("ship.enabled")
        if self.failure_classes:
            found.append("review.failure_classes")
        if self.docs_move_with_code:
            found.append("docs_move_with_code")
        return found

    def placeholders(self) -> list[str]:
        missing = []
        if not self.conventions:
            missing.append("conventions")
        if not self.codemap:
            missing.append("codemap")
        if not (self.forge_kind and self.forge_repo):
            missing.append("forge")
        if not (self.approved_label or self.block_labels or self.claim_label or self.severity_labels):
            missing.append("issues")
        if not self.gate:
            missing.append("gate")
        if not (self.worktree_root or self.worktree_provision):
            missing.append("worktree")
        if not self.ship_enabled:
            missing.append("ship")
        if not self.failure_classes:
            missing.append("review.failure_classes")
        if not self.docs_move_with_code:
            missing.append("docs_move_with_code")
        return missing


def git(cwd: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip() or None


def parse_remote(url: str) -> tuple[str | None, str | None]:
    """Return `(forge_kind, owner/name)` from a git remote URL.

    Kind is `github` or `gitlab` when the host says so, otherwise None — a
    self-hosted forge we do not recognise is not a guess we should make. The
    repo path keeps any subgroups (`group/sub/proj`); the overlay schema
    accepts that.
    """
    url = url.strip()
    if m := re.match(r"^git@([^:]+):(.+)$", url):
        host, path = m.group(1), m.group(2)
    elif m := re.match(r"^ssh://(?:git@)?([^/:]+)(?::\d+)?/(.+)$", url):
        host, path = m.group(1), m.group(2)
    elif m := re.match(r"^https?://([^/]+)/(.+)$", url):
        host, path = m.group(1), m.group(2)
    else:
        return None, None

    path = path.removesuffix(".git").strip("/")
    if not path or "/" not in path:
        return _kind_for_host(host), None
    return _kind_for_host(host), path


def _kind_for_host(host: str) -> str | None:
    host = host.lower()
    if "github" in host:
        return "github"
    if "gitlab" in host:
        return "gitlab"
    return None


def infer_branch(cwd: Path) -> str | None:
    head = git(cwd, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if head:
        return head.rsplit("/", 1)[-1]
    return None


def prefixes_from_branches(listing: str, default_branch: str | None) -> list[str]:
    """First path segment of `origin/feat/foo` is a prefix; `origin/main` is not."""
    skip = set(NOT_A_PREFIX)
    if default_branch:
        skip.add(default_branch)
    found: list[str] = []
    seen: set[str] = set()
    for line in listing.splitlines():
        line = line.strip()
        if not line or "->" in line:
            continue
        parts = line.split("/")
        # origin/feat/foo → feat. origin/main → not a prefix.
        if len(parts) < 3:
            continue
        prefix = parts[1]
        if prefix in skip or prefix in seen:
            continue
        seen.add(prefix)
        found.append(prefix)
    return found


def infer_branch_prefixes(cwd: Path, default_branch: str | None) -> list[str]:
    listing = git(cwd, "branch", "-r")
    if not listing:
        return []
    return prefixes_from_branches(listing, default_branch)


def infer_conventions(cwd: Path) -> str | None:
    for rel in CONVENTIONS_CANDIDATES:
        if (cwd / rel).is_file():
            return rel
    return None


def infer_codemap(cwd: Path) -> str | None:
    for rel in CODEMAP_CANDIDATES:
        if (cwd / rel).is_file():
            return rel
    return None


def codemap_command() -> str:
    """The command a project overlay stores so later sessions regenerate the map."""
    return f"python3 {profile_label()}/scripts/gen_codemap.py"


def generate_codemap(cwd: Path) -> int:
    script = REPO / "scripts" / "gen_codemap.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(cwd)],
        cwd=cwd,
    )
    return proc.returncode


def install_wrappers(cwd: Path) -> int:
    """Write generated skill pointers into the checkout and gitignore them."""
    script = REPO / "scripts" / "gen_agent_wrappers.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--repo", str(cwd)],
        cwd=cwd,
    )
    return proc.returncode


def overlay_path(cwd: Path) -> Path:
    """`docs/` when the project already has one, otherwise the root."""
    if (cwd / "docs").is_dir():
        return Path("docs") / "agent-overlay.yaml"
    return Path("agent-overlay.yaml")


def inspect(cwd: Path) -> Overlay:
    url = git(cwd, "remote", "get-url", "origin") or ""
    kind, repo = parse_remote(url) if url else (None, None)
    default_branch = infer_branch(cwd)
    return Overlay(
        name=cwd.name,
        conventions=infer_conventions(cwd),
        codemap=infer_codemap(cwd),
        forge_kind=kind,
        forge_repo=repo,
        default_branch=default_branch,
        branch_prefixes=infer_branch_prefixes(cwd, default_branch),
        target=overlay_path(cwd),
    )


# --- interview --------------------------------------------------------------

def _note(msg: str) -> None:
    print(msg, file=sys.stderr)


def _read(prompt: str) -> str:
    sys.stderr.write(prompt)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if line == "":
        raise SystemExit("aborted")
    return line.strip()


def ask(prompt: str, default: str | None = None) -> str | None:
    """Return the typed value, the default on empty, or None if cleared with '-'."""
    hint = f" [{default}]" if default else " [-]"
    raw = _read(f"{prompt}{hint}: ")
    if raw == CLEAR:
        return None
    if raw == "":
        return default
    return raw


def ask_choice(prompt: str, choices: tuple[str, ...], default: str) -> str:
    shown = "/".join(choices)
    while True:
        raw = ask(f"{prompt} ({shown})", default)
        if raw in choices:
            return raw
        _note(f"  choose one of: {shown}")


def ask_yesno(prompt: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = _read(f"{prompt} [{hint}]: ").lower()
        if raw == "":
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        _note("  y or n")


def ask_lines(prompt: str) -> list[str]:
    _note(prompt)
    _note("  one per line, empty line to finish")
    lines: list[str] = []
    while True:
        raw = _read(f"  {len(lines) + 1}. ")
        if raw == "":
            return lines
        if raw == CLEAR:
            return []
        lines.append(raw)


def _warn_missing(cwd: Path, rel: str | None, what: str) -> None:
    if rel and not (cwd / rel).exists():
        _note(f"  note: {rel} does not exist yet — left as a placeholder for {what}")


def interview(info: Overlay, cwd: Path) -> Overlay:
    """Fill every key by asking. Enter keeps the inference; '-' clears it."""
    _note(f"Bind {cwd} to the profile workflows.")
    _note("Enter keeps the value in [brackets]. '-' clears an optional value.")
    _note("Ctrl-C aborts. Nothing is written until the recap.")
    _note("")

    _note("== Project ==")
    info.name = ask("Name, as used in prose", info.name) or cwd.name
    info.conventions = ask(
        "Conventions doc (idioms, gotchas)", info.conventions
    )
    _warn_missing(cwd, info.conventions, "conventions")
    existing_map = info.codemap
    if existing_map:
        if ask_yesno(f"Keep the existing code map ({existing_map})?", True):
            info.install_codemap = ask_yesno("Regenerate it now from tracked sources?", False)
        else:
            info.codemap = None
            info.install_codemap = ask_yesno(
                "Generate a new committed code map from tracked sources?", True
            )
    else:
        info.install_codemap = ask_yesno(
            "Generate a committed code map from tracked sources?", True
        )
    if info.install_codemap:
        info.codemap = existing_map or "docs/CODEMAP.md"
        cmd = codemap_command()
        if cmd not in info.docs_move_with_code:
            info.docs_move_with_code.insert(0, cmd)
        _note(f"  will write {info.codemap} and set docs_move_with_code to regenerate it")
    elif info.codemap:
        _warn_missing(cwd, info.codemap, "codemap")
    info.primary_checkout = ask_choice(
        "Primary checkout — read-only if several sessions share this tree",
        ("read-only", "writable"),
        info.primary_checkout,
    )
    _note("")

    _note("== Forge ==")
    kind_default = info.forge_kind or "github"
    info.forge_kind = ask_choice("Forge", ("github", "gitlab"), kind_default)
    repo = ask("Forge repo (owner/name)", info.forge_repo)
    if repo and "/" not in repo:
        _note("  a forge repo is owner/name — leaving it unset")
        repo = None
    info.forge_repo = repo
    info.default_branch = ask("Default branch", info.default_branch or "main")
    if info.branch_prefixes:
        _note("  branch prefixes (from origin): " + ", ".join(info.branch_prefixes))
    else:
        _note("  no branch prefixes on origin — left as a placeholder")
    _note("")

    _note("== Issues ==")
    _note("A yes writes the standard name and creates the label on the forge")
    _note("if it is missing. Agents never set the approval or claim labels.")
    if ask_yesno(f"Approval queue ({DEFAULT_APPROVED})?", True):
        info.approved_label = DEFAULT_APPROVED
    else:
        info.approved_label = None
    if ask_yesno(f"Claim label, so a session can mark an issue in progress ({DEFAULT_CLAIM})?", True):
        info.claim_label = DEFAULT_CLAIM
    else:
        info.claim_label = None
    if ask_yesno(f"Block label for issues that need a human decision ({DEFAULT_BLOCK})?", True):
        info.block_labels = [DEFAULT_BLOCK]
    else:
        info.block_labels = []
    scheme = ask_choice(
        "Severity scheme",
        ("none", "p0", "severity"),
        "none",
    )
    if scheme == "p0":
        info.severity_labels = list(SEVERITY_P0)
    elif scheme == "severity":
        info.severity_labels = list(SEVERITY_WORDS)
    else:
        info.severity_labels = []
    wanted = info.issue_labels()
    if wanted:
        _note("  will create if missing: " + ", ".join(wanted))
    _note("")

    _note("== Gate ==")
    info.gate = ask_lines(
        "Commands that must all pass before a push. Empty = placeholder "
        "(a workflow will then ask rather than invent a gate)."
    )
    _note("")

    _note("== Worktree ==")
    info.worktree_root = ask(
        "Worktree root, <slug> substituted", info.worktree_root
    )
    info.worktree_provision = ask(
        "Provision doc (secrets, private db, port, build)", info.worktree_provision
    )
    _warn_missing(cwd, info.worktree_provision, "worktree.provision")
    _note("")

    _note("== Ship ==")
    want_ship = ask_yesno(
        "May a workflow go past an open pull request (tag, release, deploy, close)?",
        info.ship_enabled,
    )
    if want_ship:
        info.ship_authorization = ask_choice(
            "Authorization",
            ("ask", "pre-authorized"),
            info.ship_authorization or "ask",
        )
        procedure = ask(
            "Release/deploy procedure (repo-relative path)", info.ship_procedure
        )
        if procedure:
            info.ship_enabled = True
            info.ship_procedure = procedure
            _warn_missing(cwd, procedure, "ship.procedure")
        else:
            info.ship_enabled = False
            info.ship_procedure = None
            _note("  shipping with no procedure is incoherent — leaving enabled: false")
    else:
        info.ship_enabled = False
        if not info.ship_procedure:
            info.ship_procedure = ask(
                "Placeholder path for a future release doc", None
            )
    _note("")

    _note("== Review & generated docs ==")
    fallback = info.failure_classes or info.conventions
    info.failure_classes = ask(
        "Silent-failure list (defaults to the conventions doc)", fallback
    )
    _warn_missing(cwd, info.failure_classes, "review.failure_classes")
    extra_docs = ask_lines(
        "Other commands to run when a change moves a generated doc"
        + (" (the code-map generator is already included)." if info.install_codemap else ".")
    )
    for cmd in extra_docs:
        if cmd not in info.docs_move_with_code:
            info.docs_move_with_code.append(cmd)
    _note("")
    return info


def recap(info: Overlay, cwd: Path) -> bool:
    target = cwd / info.target
    _note(f"About to write {target}")
    _note("set:          " + ", ".join(info.decided()))
    missing = info.placeholders()
    if missing:
        _note("placeholders: " + ", ".join(missing))
    labels = info.issue_labels()
    if labels:
        _note("labels:       " + ", ".join(labels) + "  (create on the forge if missing)")
    if info.install_codemap:
        _note(f"codemap:      generate {info.codemap} from tracked sources")
    _note(
        "wrappers:     generate into .claude/skills, .codex/skills, "
        ".opencode/skills, .agents/skills (gitignored)"
    )
    return ask_yesno("Write this overlay?", True)


# --- forge labels -----------------------------------------------------------

def _run(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def list_forge_labels(cwd: Path, kind: str, repo: str) -> set[str] | None:
    """Existing label names, or None if the CLI is missing or the call failed."""
    if kind == "github":
        proc = _run(cwd, ["gh", "label", "list", "-R", repo, "--json", "name", "--limit", "1000"])
        if proc.returncode != 0:
            return None
        try:
            return {row["name"] for row in json.loads(proc.stdout)}
        except (json.JSONDecodeError, TypeError, KeyError):
            return None
    if kind == "gitlab":
        proc = _run(cwd, ["glab", "label", "list", "-R", repo, "-F", "json", "-P", "100"])
        if proc.returncode != 0:
            return None
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return None
        names: set[str] = set()
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict) and row.get("name"):
                    names.add(str(row["name"]))
        return names
    return None


def create_forge_label(cwd: Path, kind: str, repo: str, name: str) -> str | None:
    """Create `name`. Return None on success, or a short error string."""
    description, color = LABEL_META.get(name, GENERIC_LABEL)
    if kind == "github":
        proc = _run(
            cwd,
            ["gh", "label", "create", name, "-R", repo, "-d", description, "-c", color],
        )
    elif kind == "gitlab":
        proc = _run(
            cwd,
            [
                "glab", "label", "create",
                "-R", repo, "-n", name, "-d", description, "-c", f"#{color}",
            ],
        )
    else:
        return f"unknown forge {kind}"
    if proc.returncode == 0:
        return None
    err = (proc.stderr or proc.stdout or "command failed").strip().splitlines()
    return err[0] if err else "command failed"


def ensure_labels(cwd: Path, info: Overlay) -> int:
    """Create every overlay label the forge does not already have.

    This is the operator's job at setup time. Workflows must never create a
    label — a name in the overlay that the forge lacks is an error they report.
    """
    names = info.issue_labels()
    if not names:
        return 0
    if not (info.forge_kind and info.forge_repo):
        _note("labels not created: forge.kind / forge.repo unset")
        return 0

    existing = list_forge_labels(cwd, info.forge_kind, info.forge_repo)
    if existing is None:
        _note(
            f"could not list labels on {info.forge_repo} "
            f"(is the {('gh' if info.forge_kind == 'github' else 'glab')} CLI logged in?)"
        )
        return 1

    missing = [n for n in names if n not in existing]
    if not missing:
        _note("forge labels already present: " + ", ".join(names))
        return 0

    failed = 0
    for name in missing:
        err = create_forge_label(cwd, info.forge_kind, info.forge_repo, name)
        if err:
            _note(f"label {name!r}: {err}")
            failed += 1
        else:
            _note(f"created label {name}")
    already = [n for n in names if n in existing]
    if already:
        _note("already on the forge: " + ", ".join(already))
    return failed


# --- render -----------------------------------------------------------------

def _comment_block(lines: list[str]) -> list[str]:
    return [line if line.startswith("#") or line == "" else f"# {line}" for line in lines]


def render(info: Overlay) -> str:
    """A file a human can edit, not a dump of a dict.

    Every key the contract defines appears: as a real binding if it was
    decided, as a commented placeholder if it was not. The next person (or
    agent) can see what is missing and why.
    """
    lines = [
        f"# Bindings for the repo-independent agent workflows ({profile_label()}).",
        "# Steps live there and name nothing that belongs to this project; this",
        "# file supplies every name they need. Contract + defaults:",
        f"#   {profile_label()}/references/project-overlay.md",
        "#",
        "# Generated by agent-workflows/scripts/setup_repo.py.",
        "# Edit freely — this file is the project's, not the profile's.",
        "# Commented keys are placeholders: the conservative default applies",
        "# until you fill them in.",
        "",
        "schema: 1",
        "",
        "project:",
        f"  name: {yaml_str(info.name)}",
    ]
    if info.conventions:
        lines.append(f"  conventions: {yaml_str(info.conventions)}")
    else:
        lines.append("  # conventions: AGENTS.md   # idioms and gotchas; unset: read the README")
    if info.codemap:
        lines.append(f"  codemap: {yaml_str(info.codemap)}")
    else:
        lines.append("  # codemap: docs/CODEMAP.md")
    lines.append(f"  primary_checkout: {info.primary_checkout}")
    lines.append("")

    if info.forge_kind and info.forge_repo:
        lines += [
            "forge:",
            f"  kind: {info.forge_kind}",
            f"  repo: {yaml_str(info.forge_repo)}",
        ]
        if info.default_branch:
            lines.append(f"  default_branch: {yaml_str(info.default_branch)}")
        if info.branch_prefixes:
            lines.append("  branch_prefixes: [" + ", ".join(yaml_str(p) for p in info.branch_prefixes) + "]")
        else:
            lines.append("  # branch_prefixes: [feat, fix, perf, chore, docs]")
    else:
        lines += _comment_block([
            "forge:",
            "  kind: github                 # or gitlab; unset: infer from origin",
            "  repo: owner/name",
            f"  default_branch: {info.default_branch or 'main'}",
            "  branch_prefixes: [feat, fix]",
        ])
    lines.append("")

    if info.approved_label or info.block_labels or info.claim_label or info.severity_labels:
        lines.append("issues:")
        if info.approved_label:
            lines.append(f"  approved_label: {yaml_str(info.approved_label)}")
        else:
            lines.append("  # approved_label: approved   # agents never set this")
        if info.block_labels:
            lines.append("  block_labels: [" + ", ".join(yaml_str(x) for x in info.block_labels) + "]")
        else:
            lines.append("  # block_labels: [blocked]")
        if info.claim_label:
            lines.append(f"  claim_label: {yaml_str(info.claim_label)}")
        else:
            lines.append("  # claim_label: in-progress   # unset: no claiming protocol")
        if info.severity_labels:
            lines.append("  severity_labels: [" + ", ".join(yaml_str(x) for x in info.severity_labels) + "]")
        else:
            lines.append("  # severity_labels: [P0, P1, P2]")
        lines.append("  never_set: [" + ", ".join(yaml_str(x) for x in info.never_set()) + "]")
    else:
        lines += _comment_block([
            "issues:",
            "  approved_label: approved     # cleared to build; agents never set it",
            "  block_labels: [blocked]      # stop, this needs a human decision",
            "  claim_label: in-progress     # unset: no claiming protocol",
            "  severity_labels: [P0, P1, P2]",
            "  never_set: [approved, in-progress, assignee, milestone]",
        ])
    lines.append("")

    if info.gate:
        lines.append("gate:")
        for cmd in info.gate:
            lines.append(f"  - {yaml_str(cmd)}")
    else:
        lines += _comment_block([
            "gate:                          # unset: a workflow will ask, not invent",
            "  - <test command>",
        ])
    lines.append("")

    if info.worktree_root or info.worktree_provision:
        lines.append("worktree:")
        if info.worktree_root:
            lines.append(f"  root: {yaml_str(info.worktree_root)}")
        else:
            lines.append("  # root: ../<repo>-<slug>")
        if info.worktree_provision:
            lines.append(f"  provision: {yaml_str(info.worktree_provision)}")
        else:
            lines.append("  # provision: docs/worktrees.md")
    else:
        lines += _comment_block([
            "worktree:",
            "  root: ../<repo>-<slug>",
            "  provision: docs/worktrees.md  # secrets, private db, port, asset build",
        ])
    lines.append("")

    if info.ship_enabled and info.ship_procedure:
        lines += [
            "ship:",
            "  enabled: true",
            f"  authorization: {info.ship_authorization}",
            f"  procedure: {yaml_str(info.ship_procedure)}",
        ]
    else:
        lines += [
            "ship:",
            "  enabled: false               # workflows stop at an open pull request",
        ]
        if info.ship_procedure:
            lines.append(f"  # procedure: {yaml_str(info.ship_procedure)}")
        else:
            lines.append("  # authorization: ask          # or pre-authorized")
            lines.append("  # procedure: docs/release.md  # required before enabled: true")
    lines.append("")

    if info.failure_classes:
        lines += [
            "review:",
            f"  failure_classes: {yaml_str(info.failure_classes)}",
        ]
    else:
        lines += _comment_block([
            "review:",
            "  failure_classes: AGENTS.md   # unset: falls back to project.conventions",
        ])
    lines.append("")

    if info.docs_move_with_code:
        lines.append("docs_move_with_code:")
        for cmd in info.docs_move_with_code:
            lines.append(f"  - {yaml_str(cmd)}")
    else:
        lines += _comment_block([
            "docs_move_with_code:",
            "  - <regenerate the code map>",
        ])
    lines.append("")
    return "\n".join(lines)


def self_test() -> int:
    """Remote parsing and rendering, no checkout required.

    The command is the thing a stranger's repo will run first. If URL parsing
    quietly returns None, every overlay it writes is missing the forge and the
    only symptom is an agent asking a question it should not have to.
    """
    cases = (
        ("git@github.com:owner/name.git", "github", "owner/name"),
        ("https://github.com/owner/name.git", "github", "owner/name"),
        ("https://github.com/owner/name", "github", "owner/name"),
        ("git@gitlab.com:group/sub/proj.git", "gitlab", "group/sub/proj"),
        ("https://gitlab.example.com/group/proj.git", "gitlab", "group/proj"),
        ("ssh://git@gitlab.example.com:2222/group/proj.git", "gitlab", "group/proj"),
        ("git@git.example.com:owner/name.git", None, "owner/name"),
        ("not-a-remote", None, None),
    )
    failed = 0
    for url, want_kind, want_repo in cases:
        kind, repo = parse_remote(url)
        if (kind, repo) != (want_kind, want_repo):
            print(
                f"parse_remote({url!r}) = {(kind, repo)!r}, "
                f"expected {(want_kind, want_repo)!r}",
                file=sys.stderr,
            )
            failed += 1

    prefix_listing = (
        "  origin/HEAD -> origin/main\n"
        "  origin/main\n"
        "  origin/feat/foo\n"
        "  origin/feat/bar\n"
        "  origin/fix/one\n"
        "  origin/chore/deps\n"
        "  origin/staging\n"
    )
    prefixes = prefixes_from_branches(prefix_listing, "main")
    if prefixes != ["feat", "fix", "chore"]:
        print(f"prefixes_from_branches = {prefixes!r}, expected ['feat', 'fix', 'chore']", file=sys.stderr)
        failed += 1

    full = Overlay(
        name="example",
        target=Path("docs/agent-overlay.yaml"),
        conventions="CONTRIBUTING.md",
        codemap="docs/CODEMAP.md",
        primary_checkout="read-only",
        forge_kind="github",
        forge_repo="owner/name",
        default_branch="main",
        branch_prefixes=["feat", "fix"],
        approved_label="approved",
        block_labels=["blocked"],
        claim_label="in-progress",
        severity_labels=["P0", "P1"],
        gate=["npm test"],
        worktree_root="../example-<slug>",
        worktree_provision="docs/worktrees.md",
        ship_enabled=True,
        ship_authorization="ask",
        ship_procedure="docs/release.md",
        failure_classes="CONTRIBUTING.md",
        docs_move_with_code=["make map"],
    )
    if full.issue_labels() != ["approved", "blocked", "in-progress", "P0", "P1"]:
        print(f"issue_labels = {full.issue_labels()!r}", file=sys.stderr)
        failed += 1
    rendered = render(full)
    for needle in (
        "schema: 1",
        "name: example",
        "conventions: CONTRIBUTING.md",
        "codemap: docs/CODEMAP.md",
        "kind: github",
        "repo: owner/name",
        "default_branch: main",
        "primary_checkout: read-only",
        "approved_label: approved",
        "gate:",
        "  - npm test",
        "enabled: true",
        "procedure: docs/release.md",
        "docs_move_with_code:",
    ):
        if needle not in rendered:
            print(f"rendered overlay missing {needle!r}", file=sys.stderr)
            failed += 1

    bare = render(Overlay(name="bare", target=Path("agent-overlay.yaml")))
    for needle in (
        "# conventions:",
        "# gate:",
        "enabled: false",
        "# procedure:",
        "# issues:",
    ):
        if needle not in bare:
            print(f"placeholder overlay missing {needle!r}", file=sys.stderr)
            failed += 1

    # A decided gate must not be commented; a skipped gate must.
    if any(line.startswith("gate:") for line in bare.splitlines()):
        print("bare overlay wrote a live gate with no commands", file=sys.stderr)
        failed += 1
    if "# conventions: AGENTS.md" not in bare:
        print("bare overlay lost the conventions placeholder", file=sys.stderr)
        failed += 1

    try:
        import yaml
        from jsonschema import Draft202012Validator
    except ImportError:
        validator = None
    else:
        schema = json.loads((REPO / "overlay.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)

    if validator is not None:
        samples = [rendered, bare]
        for sample in samples:
            data = yaml.safe_load(sample)
            for err in validator.iter_errors(data):
                where = ".".join(str(p) for p in err.path) or "(root)"
                print(f"rendered overlay {where}: {err.message}", file=sys.stderr)
                failed += 1

    if failed:
        return 1
    extra = f", {len(samples)} overlays against schema" if validator is not None else ""
    print(f"setup_repo self-test passed ({len(cases)} remotes{extra})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "dir",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="project checkout (default: current directory)",
    )
    ap.add_argument("--force", action="store_true", help="overwrite an existing overlay")
    ap.add_argument(
        "--print",
        action="store_true",
        dest="print_only",
        help="write the overlay to stdout, not to disk",
    )
    ap.add_argument(
        "--non-interactive",
        action="store_true",
        help="do not interview; write inferences and placeholders only",
    )
    ap.add_argument(
        "--create-labels",
        action="store_true",
        help="create missing forge labels even when not interviewing",
    )
    ap.add_argument(
        "--no-create-labels",
        action="store_true",
        help="do not create forge labels, even after an interview",
    )
    ap.add_argument(
        "--generate-codemap",
        action="store_true",
        help="generate docs/CODEMAP.md even when not interviewing",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="assert remote parsing and rendering still work, and exit",
    )
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    cwd = args.dir.resolve()
    if not (cwd / ".git").exists():
        print(f"{cwd}: not a git checkout (no .git)", file=sys.stderr)
        return 2

    interactive = (not args.non_interactive) and sys.stdin.isatty()
    info = inspect(cwd)
    if args.generate_codemap and not interactive:
        info.install_codemap = True
        info.codemap = info.codemap or "docs/CODEMAP.md"
        cmd = codemap_command()
        if cmd not in info.docs_move_with_code:
            info.docs_move_with_code.insert(0, cmd)
    target = cwd / info.target

    if target.exists() and not args.force and not args.print_only:
        if interactive:
            if not ask_yesno(f"{target} already exists. Replace it?", False):
                print("aborted", file=sys.stderr)
                return 2
        else:
            print(
                f"{target}: already exists. Edit it, or rerun with --force to replace it.",
                file=sys.stderr,
            )
            return 2

    if interactive:
        try:
            info = interview(info, cwd)
        except KeyboardInterrupt:
            print("\naborted", file=sys.stderr)
            return 130

    text = render(info)

    if args.print_only and not interactive:
        sys.stdout.write(text)
        return 0

    if interactive and not recap(info, cwd):
        print("aborted", file=sys.stderr)
        return 2

    if args.print_only:
        sys.stdout.write(text)
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

    _note(f"wrote {target}")
    _note("set:          " + ", ".join(info.decided()))
    missing = info.placeholders()
    if missing:
        _note("placeholders: " + ", ".join(missing))
        _note("edit the file to fill the placeholders when those facts exist.")

    create = (interactive or args.create_labels) and not args.no_create_labels
    if create and info.issue_labels():
        if ensure_labels(cwd, info) != 0:
            return 1
    if info.install_codemap:
        _note(f"generating {info.codemap} from tracked sources")
        if generate_codemap(cwd) != 0:
            return 1
    _note("installing generated skill wrappers and gitignoring them")
    if install_wrappers(cwd) != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
