#!/usr/bin/env python3
"""Generate a deterministic code map from a checkout's tracked files.

A map a human maintains goes stale, and a stale map is worse than no map. This
script derives the structural half — layout, languages, Python symbols, ORM
tables, HTTP routes, tests — from ``git ls-files`` and writes it under
``docs/``. Regenerating is the whole maintenance story; ``--check`` fails if
the committed copy is behind the code.

Stack-specific extractors fire only when they find something, so a docs repo
does not grow an empty Tables section. Extending an extractor for one
codebase belongs in that codebase; the recipe is
``skills/generating-code-maps/``.

The script never opens a database, never imports the project, and never
reads ``.env``. A ``--check`` failure means exactly one thing: the map is
behind the code.

Usage::

    python3 scripts/gen_codemap.py                  # this repo
    python3 scripts/gen_codemap.py --root /path     # any checkout
    python3 scripts/gen_codemap.py --check
    python3 scripts/gen_codemap.py --self-test
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

PROFILE = Path(__file__).resolve().parent.parent

SKELETON = Path("docs/CODEMAP.md")
PYTHON_DOC = Path("docs/codemap/python.md")
ROUTES_DOC = Path("docs/codemap/routes.md")
TABLES_DOC = Path("docs/codemap/tables.md")

HTTP_VERBS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "route"})
ROUTER_NAMES = frozenset({"router", "app", "api", "bp", "blueprint"})
LANG_BY_SUFFIX = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".php": "PHP",
    ".sh": "Shell",
    ".bash": "Shell",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
}


def git_ls_files(root: Path, *patterns: str) -> list[str]:
    """Tracked paths, sorted. A filesystem walk would pick up scratch files."""
    cmd = ["git", "ls-files", "-z", "--", *patterns] if patterns else ["git", "ls-files", "-z"]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"{root}: not a git checkout (git ls-files failed)")
    return sorted(p for p in proc.stdout.split("\0") if p)


def read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def parse_python(root: Path, rel: str) -> ast.Module | None:
    try:
        return ast.parse(read(root, rel), filename=rel)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None


def _const_str(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def is_test_path(rel: str) -> bool:
    name = Path(rel).name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if name.endswith((".test.js", ".test.ts", ".test.tsx", ".spec.js", ".spec.ts", ".spec.tsx")):
        return True
    parts = Path(rel).parts
    return "tests" in parts or "test" in parts or "__tests__" in parts


def top_dir(rel: str) -> str:
    parts = Path(rel).parts
    return parts[0] + "/" if len(parts) > 1 else "(root)"


def language_of(rel: str) -> str | None:
    return LANG_BY_SUFFIX.get(Path(rel).suffix.lower())


# --- extractors -------------------------------------------------------------


@dataclass
class PyModule:
    path: str
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)


@dataclass
class Table:
    name: str
    cls: str
    path: str


@dataclass
class Route:
    method: str
    path: str
    handler: str
    file: str


def collect_python(root: Path, py_files: list[str]) -> list[PyModule]:
    modules: list[PyModule] = []
    for rel in py_files:
        tree = parse_python(root, rel)
        if tree is None:
            continue
        classes: list[str] = []
        functions: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                functions.append(node.name)
        if classes or functions:
            modules.append(PyModule(rel, classes, functions))
    return modules


def collect_tables(root: Path, py_files: list[str]) -> list[Table]:
    tables: list[Table] = []
    seen: set[str] = set()
    for rel in py_files:
        tree = parse_python(root, rel)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                targets = (
                    stmt.targets
                    if isinstance(stmt, ast.Assign)
                    else [stmt.target]
                    if isinstance(stmt, ast.AnnAssign)
                    else []
                )
                names = [t.id for t in targets if isinstance(t, ast.Name)]
                if "__tablename__" not in names:
                    continue
                name = _const_str(getattr(stmt, "value", None))
                if name and name not in seen:
                    seen.add(name)
                    tables.append(Table(name, node.name, rel))
    return sorted(tables, key=lambda t: (t.name, t.path))


def _route_from_decorator(dec: ast.AST, handler: str, file: str, prefix: str) -> Route | None:
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return None
    verb = dec.func.attr.lower()
    if verb not in HTTP_VERBS:
        return None
    if not (isinstance(dec.func.value, ast.Name) and dec.func.value.id in ROUTER_NAMES):
        return None
    url = _const_str(dec.args[0]) if dec.args else None
    if url is None:
        return None
    method = "ANY" if verb == "route" else verb.upper()
    if verb == "route":
        for kw in dec.keywords:
            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                methods = [_const_str(e) for e in kw.value.elts]
                methods = [m.upper() for m in methods if m]
                if methods:
                    method = "/".join(sorted(methods))
    return Route(method, f"{prefix}{url}" or "/", handler, file)


def collect_routes(root: Path, py_files: list[str]) -> list[Route]:
    routes: list[Route] = []
    for rel in py_files:
        tree = parse_python(root, rel)
        if tree is None:
            continue
        prefix = ""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id in ROUTER_NAMES for t in node.targets):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            for kw in node.value.keywords:
                if kw.arg == "prefix":
                    prefix = _const_str(kw.value) or ""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                route = _route_from_decorator(dec, node.name, rel, prefix)
                if route:
                    routes.append(route)
    return sorted(routes, key=lambda r: (r.path, r.method, r.file))


def collect_makefile_targets(root: Path, files: list[str]) -> list[str]:
    if "Makefile" not in files:
        return []
    targets: list[str] = []
    for line in read(root, "Makefile").splitlines():
        if line.startswith("\t") or line.startswith("#") or ":" not in line:
            continue
        name, _, rest = line.partition(":")
        name = name.strip()
        # `PY := ...` is an assignment, not a target.
        if rest.startswith("=") or name.endswith("?"):
            continue
        if name and " " not in name and name != ".PHONY":
            targets.append(name)
    return sorted(set(targets))


def collect_npm_scripts(root: Path, files: list[str]) -> list[tuple[str, str]]:
    if "package.json" not in files:
        return []
    try:
        data = json.loads(read(root, "package.json"))
    except json.JSONDecodeError:
        return []
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return []
    return sorted((str(k), str(v)) for k, v in scripts.items())


# --- render -----------------------------------------------------------------


def _banner(root: Path) -> list[str]:
    try:
        here = "~/" + str(PROFILE.relative_to(Path.home()))
    except ValueError:
        here = str(PROFILE)
    relative = root.resolve() == PROFILE.resolve()
    regen = "`make map`" if relative else f"`python3 {here}/scripts/gen_codemap.py`"
    check = "`make map-check`" if relative else f"`python3 {here}/scripts/gen_codemap.py --check`"
    return [
        f"<!-- GENERATED by {here}/scripts/gen_codemap.py — DO NOT EDIT.",
        f"     {regen} regenerates; {check} fails if this is behind the code. -->",
        "",
    ]


def _md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _join(items: list[str], empty: str = "—") -> str:
    return ", ".join(f"`{i}`" for i in items) if items else empty


def render_skeleton(
    root: Path,
    files: list[str],
    languages: Counter[str],
    layout: list[tuple[str, int]],
    py_modules: list[PyModule],
    tables: list[Table],
    routes: list[Route],
    make_targets: list[str],
    npm_scripts: list[tuple[str, str]],
    tests: list[str],
) -> str:
    py_files = [f for f in files if f.endswith(".py")]
    glance: list[list[str]] = [
        ["Tracked files", str(len(files))],
        ["Languages", ", ".join(f"{n} {lang}" for lang, n in languages.most_common())],
        ["Tests", str(len(tests))],
    ]
    if py_files:
        glance.append(["Python files", str(len(py_files))])
        glance.append(["Python modules with public symbols", str(len(py_modules))])
    if tables:
        glance.append(["ORM tables (`__tablename__`)", str(len(tables))])
    if routes:
        glance.append(["HTTP routes", str(len(routes))])
    if make_targets:
        glance.append(["Make targets", str(len(make_targets))])
    if npm_scripts:
        glance.append(["npm scripts", str(len(npm_scripts))])

    lines = _banner(root)
    lines += [
        "# Code map",
        "",
        "The **derived** half of this repo's agent context: what the codebase *is*",
        "right now. Judgment — invariants, idioms, gotchas — belongs in the",
        "project's conventions document and is written by hand.",
        "",
        "Generated from tracked sources only — no database, no `.env`, no import",
        "of the project. A `--check` failure means exactly one thing: **the map",
        "is behind the code, regenerate it.**",
        "",
        "## At a glance",
        "",
    ]
    lines += _md_table(["", ""], glance)
    lines += ["", "## Layout", ""]
    lines += _md_table(["Path", "Files"], [[f"`{p}`", str(n)] for p, n in layout])

    if make_targets:
        lines += ["", "## Make targets", "", _join(make_targets)]
    if npm_scripts:
        lines += ["", "## npm scripts", ""]
        lines += _md_table(["Script", "Command"], [[f"`{k}`", f"`{v}`"] for k, v in npm_scripts])

    if py_modules:
        lines += [
            "",
            "## Python",
            "",
            f"{len(py_modules)} modules expose a public class or function. Full list:",
            f"[codemap/python.md]({PYTHON_DOC.relative_to(SKELETON.parent)}).",
        ]
    if tables:
        lines += [
            "",
            "## Tables",
            "",
            f"{len(tables)} `__tablename__` declarations. Full list:",
            f"[codemap/tables.md]({TABLES_DOC.relative_to(SKELETON.parent)}).",
        ]
    if routes:
        lines += [
            "",
            "## HTTP routes",
            "",
            f"{len(routes)} decorator-declared routes. Full list:",
            f"[codemap/routes.md]({ROUTES_DOC.relative_to(SKELETON.parent)}).",
        ]
    if tests:
        by_dir: Counter[str] = Counter(top_dir(t) for t in tests)
        lines += ["", "## Tests", ""]
        lines += _md_table(
            ["Path", "Files"],
            [[f"`{p}`", str(n)] for p, n in sorted(by_dir.items())],
        )
    lines.append("")
    return "\n".join(lines)


def render_python(root: Path, modules: list[PyModule]) -> str:
    lines = _banner(root)
    lines += [
        "# Python symbols",
        "",
        "Module-level public classes and functions, from `ast`. Nested and",
        "private (`_`-prefixed) names are omitted. Empty does not mean unused.",
        "",
    ]
    rows = []
    for mod in modules:
        rows.append([f"`{mod.path}`", _join(mod.classes), _join(mod.functions)])
    lines += _md_table(["Module", "Classes", "Functions"], rows)
    lines.append("")
    return "\n".join(lines)


def render_tables(root: Path, tables: list[Table]) -> str:
    lines = _banner(root)
    lines += [
        "# Tables",
        "",
        "Every `__tablename__` assigned on a class. Matched via `ast`, not a live",
        "database — a model that builds its name at runtime is invisible here.",
        "",
    ]
    lines += _md_table(
        ["Table", "Class", "Defined in"],
        [[f"`{t.name}`", f"`{t.cls}`", f"`{t.path}`"] for t in tables],
    )
    lines.append("")
    return "\n".join(lines)


def render_routes(root: Path, routes: list[Route]) -> str:
    lines = _banner(root)
    lines += [
        "# HTTP routes",
        "",
        "Decorator-declared routes on `router` / `app` / `api` / `bp`. Two",
        "handlers for one path are listed twice — that is the bug the map is",
        "meant to surface. Anything registered at runtime is invisible.",
        "",
    ]
    lines += _md_table(
        ["Method", "Path", "Handler", "File"],
        [[r.method, f"`{r.path}`", f"`{r.handler}`", f"`{r.file}`"] for r in routes],
    )
    lines.append("")
    return "\n".join(lines)


def build(root: Path) -> dict[str, str]:
    """Every generated file, keyed by repo-relative path."""
    files = git_ls_files(root)
    languages: Counter[str] = Counter()
    layout_counter: Counter[str] = Counter()
    for rel in files:
        layout_counter[top_dir(rel)] += 1
        lang = language_of(rel)
        if lang:
            languages[lang] += 1
    layout = sorted(layout_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    tests = [f for f in files if is_test_path(f)]
    py_files = [f for f in files if f.endswith(".py")]
    py_modules = collect_python(root, py_files)
    tables = collect_tables(root, py_files)
    routes = collect_routes(root, py_files)
    make_targets = collect_makefile_targets(root, files)
    npm_scripts = collect_npm_scripts(root, files)

    out: dict[str, str] = {
        str(SKELETON): render_skeleton(
            root, files, languages, layout, py_modules, tables, routes,
            make_targets, npm_scripts, tests,
        )
    }
    if py_modules:
        out[str(PYTHON_DOC)] = render_python(root, py_modules)
    if tables:
        out[str(TABLES_DOC)] = render_tables(root, tables)
    if routes:
        out[str(ROUTES_DOC)] = render_routes(root, routes)
    return out


def write(root: Path, want: dict[str, str]) -> tuple[int, int]:
    written = 0
    for rel, text in want.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            written += 1
    # Detail files we used to emit but no longer should go away, otherwise a
    # repo that lost its last route would keep a stale routes.md forever.
    known = {SKELETON, PYTHON_DOC, ROUTES_DOC, TABLES_DOC}
    removed = 0
    codemap_dir = root / "docs" / "codemap"
    if codemap_dir.is_dir():
        for path in sorted(codemap_dir.glob("*.md")):
            rel = path.relative_to(root).as_posix()
            if Path(rel) in known and rel not in want:
                path.unlink()
                removed += 1
    return written, removed


def check(root: Path, want: dict[str, str]) -> int:
    drifted: list[str] = []
    for rel, text in sorted(want.items()):
        path = root / rel
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            drifted.append(rel)
    if drifted:
        print("the committed map no longer matches the code:", file=sys.stderr)
        for rel in drifted:
            print(f"  {rel}", file=sys.stderr)
        print("\nFix: run `python3 scripts/gen_codemap.py` (or `make map`).", file=sys.stderr)
        return 1
    print(f"code map is up to date ({len(want)} files)")
    return 0


def self_test() -> int:
    """Determinism plus a tiny fixture that trips every extractor."""
    first = build(PROFILE)
    second = build(PROFILE)
    if first != second:
        print("gen_codemap is not deterministic on this repo", file=sys.stderr)
        return 1

    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="codemap-"))
    try:
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
        (tmp / "app").mkdir()
        (tmp / "app" / "models.py").write_text(
            "class Item:\n    __tablename__ = 'items'\n\nclass Hidden:\n    pass\n",
            encoding="utf-8",
        )
        (tmp / "app" / "web.py").write_text(
            "router = APIRouter(prefix='/api')\n"
            "@router.get('/items')\n"
            "def list_items():\n    return []\n",
            encoding="utf-8",
        )
        (tmp / "tests").mkdir()
        (tmp / "tests" / "test_items.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        (tmp / "Makefile").write_text("map:\n\ttrue\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp, check=True)
        files = build(tmp)
        skeleton = files[str(SKELETON)]
        for needle in (
            "Tracked files",
            "ORM tables",
            "HTTP routes",
            "Make targets",
            "`map`",
        ):
            if needle not in skeleton:
                print(f"fixture skeleton missing {needle!r}", file=sys.stderr)
                return 1
        tables = files[str(TABLES_DOC)]
        if "`items`" not in tables or "`Item`" not in tables:
            print("fixture tables.md missed the model", file=sys.stderr)
            return 1
        routes = files[str(ROUTES_DOC)]
        if "`/api/items`" not in routes or "`list_items`" not in routes:
            print("fixture routes.md missed the handler", file=sys.stderr)
            return 1
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

    print(f"gen_codemap self-test passed (deterministic, {len(first)} files on this repo)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None, help="checkout to map (default: this repo)")
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed map is stale")
    ap.add_argument("--self-test", action="store_true", help="assert determinism and extractors")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    root = (args.root or PROFILE).resolve()
    want = build(root)
    if args.check:
        return check(root, want)

    written, removed = write(root, want)
    for rel in want:
        print(f"wrote {root / rel}")
    print(f"{written} written, {removed} removed, {len(want)} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
