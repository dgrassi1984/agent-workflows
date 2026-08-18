# agent-workflows

The procedures I want coding agents to follow, written once, installed into every
harness, and bound to a project by a small file the project owns.

## The split, and why it is the whole point

A workflow document mixes two kinds of fact, and they rot on different clocks:

| | Changes when | Lives in |
|---|---|---|
| **Procedure** — the order of steps, and what makes each one actually done | *I* change how I like to work | `workflows/` here |
| **Binding** — which forge, which labels, which command is the gate, whether this project may ship | the *project* changes | `<project>/docs/agent-overlay.yaml` |
| **Invariant** — the idioms and the failure modes this codebase has paid for | the *code* changes | the project's own conventions doc |
| **Inventory** — modules, routes, tables, jobs | constantly | generated, in the project |

Keeping the first two in one file is how a set of workflows ends up copied per
repo and disagreeing with itself. That already happened to the set these came
from: one project's review procedure had grown a second, drifting copy of the
same gotcha list its conventions file already held — each missing entries the
other had.

**A fact in the wrong tier is what makes agent documentation rot.** Everything
here follows from that.

## Layout

```
workflows/      the procedures — one file per command, frontmatter + body
references/     what several workflows share: the overlay contract, the worktree
                rule, the per-forge command dialects, the reporting contract,
                the signature vocabulary
skills/         reference skills (knowledge, not procedure), copied verbatim
scripts/        the wrapper generator, the guards, project setup, and the code map
docs/CODEMAP.md the derived map of *this* repo (regenerate with `make map`)
overlay.schema.json
```

## Using it

```bash
make install     # write every workflow and reference skill into each harness
make install-repo DIR=../myproject  # same wrappers, inside a checkout, gitignored
make check       # what CI runs: the guards + harness freshness
make overlay     # validate every project overlay under ~/Development
make setup-repo DIR=../myproject   # bind a checkout: overlay + gitignored wrappers
make map         # regenerate docs/CODEMAP.md from tracked sources
make map DIR=../myproject
```

Installed harnesses are listed in `scripts/gen_agent_wrappers.py`. Only ones whose
profile skill directory has been **confirmed on this machine** are there —
guessing a path produces a skill that silently never loads, and nothing anywhere
that says so.

| Harness | Profile directory | Invoke |
|---|---|---|
| Claude Code | `~/.claude/skills` | `/work-issue` |
| Codex | `~/.codex/skills` | `$work-issue` |
| OpenCode | `~/.config/opencode/skills` | `/work-issue` |
| DeepSeek Harness | `~/.dsh/skills` | `/work-issue` |

Each harness gets a short generated wrapper that **points** at
`workflows/<name>.md` rather than copying it: one copy on disk, and an edit takes
effect without reinstalling. The same six workflows and five reference skills
land in every harness.

## Adding a project

From the project checkout:

```bash
python3 ~/Development/agent-workflows/scripts/setup_repo.py
```

Or from this repo: `make setup-repo DIR=/path/to/project`.

That interviews on a TTY: confirms what it can see (forge, default branch, a
conventions file, branch prefixes already on `origin`) and asks the rest —
whether the checkout is shared, whether issues go through a queue, what the
gate is, whether this project may ship, whether to generate a code map.
Labels you opt into (`human-approved`, `wip`, `design-needed`, a severity
scheme) are created on the forge if they are missing. A yes to the code map
writes `docs/CODEMAP.md` from tracked sources and sets `docs_move_with_code`
so later sessions regenerate it. It also writes generated skill wrappers
into the project's harness directories (`.claude/skills`, `.codex/skills`,
`.opencode/skills`, `.agents/skills`) and adds those paths to `.gitignore`.
The overlay is the project's; the wrappers are pointers and must not be
committed. Re-run `make install-repo DIR=/path/to/project` to refresh them.
Every overlay key ends up in the file, either as a binding or as
a commented placeholder. `--non-interactive` skips the questions.
`--print` dry-runs; `--force` overwrites. The key set, and what a missing key
means, lives in `references/project-overlay.md`.

A repo with no overlay still works: every workflow falls back to conservative
defaults (read-only primary checkout, no queue, no claiming, stop at an open
pull request, never deploy).

## The two guards

Both exist because this design fails *quietly* when it fails.

- **`check_unbound.py`** — fails if a procedure names a project, a toolchain, a
  forge CLI or a label. The split is never lost by redesign; it is lost by one
  convenient sentence added while fixing something else. `make guard-test` proves
  the guard can still fail, against a fixture written to trip every rule.
- **`gen_agent_wrappers.py --check`** — fails if any harness is behind this repo.
  It removes orphans, but **only paths a previous install recorded in that
  harness's manifest**: a harness home also holds skills from plugins, other tools
  and you, and none of those are ours to delete.

## What does not belong here

- A release ritual, a deploy target, a host, a database name.
- A list of one codebase's silent failure modes. That is the least transferable
  knowledge there is and the fastest to rot away from the code that produces it;
  the overlay points at where the project keeps it.
- A count, a size, an inventory or a file list — of anything.
