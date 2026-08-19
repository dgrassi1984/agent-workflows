<!-- unbound-check: exempt — documents the key set, with a worked example -->

# The project overlay

Every workflow in this repo is a **procedure**: an order of steps, and the
judgment about what makes each step actually done. None of them can run without
also knowing a pile of **bindings**: which forge, which labels, which command is
the test gate, whether this project is allowed to ship.

Those two kinds of fact go stale for different reasons and at different times. A
procedure changes when *you* change how you like to work. A binding changes when
the *project* changes — a renamed label, a new gate, a different deploy target.
Keeping them in one file means every project's change rewrites your procedure,
and every procedure change has to be re-applied per project. That is how a set of
workflows ends up copied five times and disagreeing with itself.

So: the steps live here. The names live in the project.

## Where to look

In the repository you are working in, in this order — first hit wins:

1. `docs/agent-overlay.yaml`
2. `agent-overlay.yaml` (repo root, for projects with no `docs/`)

Read it **before** step 1 of any workflow. If neither exists, the project has not
opted in, and the defaults in *No overlay* below apply.

## Writing one

From the project checkout:

```bash
python3 ~/Development/agent-workflows/scripts/setup_repo.py
```

Or from this repo: `make setup-repo DIR=/path/to/project`.

On a TTY the command interviews: it confirms what it can see on disk (forge,
default branch, a conventions or codemap file, branch prefixes already on
`origin`) and asks the rest — checkout sharing, the issue queue, the gate,
whether this project may ship, whether to generate a code map. Issue labels
you opt into are created on the forge if they are missing (`human-approved`,
`wip`, `design-needed`, and the severity scheme you pick). A yes to the code
map writes `docs/CODEMAP.md` from tracked sources (the generator lives in
this repo) and sets `docs_move_with_code` so later sessions regenerate it.
It also writes generated skill wrappers into the project's harness
directories and adds those paths to `.gitignore` — they are pointers at
this repo, not project-owned content. After this profile gains a workflow,
refresh a bound checkout with
`python3 ~/Development/agent-workflows/scripts/setup_repo.py --update`
(or `make update-repo DIR=.` from this repo). That rewrites the wrappers
and leaves the overlay alone. An edit to an existing procedure needs no
refresh: the wrappers already point here.
Every key in this document appears in the file. A
decision becomes a binding; a skip becomes a commented placeholder with the
conservative default, so the next edit is filling a blank rather than
reconstructing the contract.

Re-running on a repo that already has an overlay still asks before replacing
the file. No — leave the overlay, refresh the wrappers. Yes — interview,
defaulting to the current bindings, so Enter keeps the gate, labels, and
ship settings. `--non-interactive --force` reuses those same live bindings
rather than wiping them back to inferences. `--update` is the non-interactive
wrapper-only path.

`--non-interactive` (or a non-TTY) writes only the inferences and the
placeholders for keys the overlay has not decided. It will not invent a
gate, a label scheme or a release ritual. It will not overwrite an existing
overlay without `--force` (or an explicit yes, when interviewing).
`--print` writes the file to stdout instead of disk.

Hand-writing the same file is fine. The command is a starter, not a requirement.

## The conflict rule

- The **overlay** wins on bindings — names, commands, hosts, labels, paths.
- **This procedure** wins on steps.
- The project's own **conventions document** (`project.conventions`) wins on
  engineering invariants — the idioms and the gotchas that repo has paid for.

Two documents disagreeing about a *step* is a bug in the docs, not a judgment
call for you. Say so, and do not silently pick one.

## The keys

Every key is optional. A missing key takes its default, and the defaults are
deliberately conservative: an under-specified project should make you cautious,
not creative.

### `schema`

`1`. Bump only when this contract changes incompatibly. An overlay with a
`schema` you do not recognise: read what you can, say what you skipped.

### `project`

| Key | Means | Default |
|---|---|---|
| `name` | what to call it in prose | the repo name |
| `conventions` | the invariants doc to read before editing (idioms, gotchas) | none — read the README and infer, and say that you did |
| `codemap` | a generated map of the codebase, if there is one | none — `setup_repo` can write `docs/CODEMAP.md` |
| `primary_checkout` | `read-only` or `writable` | **`read-only`** |

`primary_checkout: read-only` is the default because the failure it prevents is
silent: see `worktree-rule.md`. A project that genuinely has one session at a
time can set `writable` and skip the worktree.

### `forge`

| Key | Means | Default |
|---|---|---|
| `kind` | `github` or `gitlab` — picks the dialect in `forge-<kind>.md` | infer from `git remote get-url origin`; if it is neither, stop and ask |
| `repo` | `owner/name` | inferred from the remote |
| `default_branch` | what branches are cut from and merged into | `main` |
| `branch_prefixes` | the prefixes this repo actually uses | look at `git branch -r` and match |

### `issues`

| Key | Means | Default |
|---|---|---|
| `approved_label` | marks an issue cleared to build; **agents never set it** | none — work only issues the user names |
| `block_labels` | stop, do not build, this needs a human decision | `[]` |
| `claim_label` | the "a session is on this" claim | none — no claiming protocol; check branches and open PRs instead |
| `severity_labels` | the severity scheme, exactly one per issue | none — do not invent one |
| `never_set` | labels and fields an agent must not set | `[approved_label, claim_label, assignee, milestone]` |

A label named here that does not exist on the forge is an error worth reporting,
not one to fix by creating the label.

### `gate`

A list of shell commands that must all pass before anything is pushed, in order.

Default: **none, and that is a blocker, not a licence.** Find the project's test
command and confirm it with the user before pushing anything. Never invent a gate
and never report an ungated branch as verified.

### `worktree`

| Key | Means | Default |
|---|---|---|
| `root` | where sibling worktrees go, `<slug>` substituted | `../<repo>-<slug>` |
| `provision` | a doc describing what a fresh worktree still needs (secrets, a private database, a port, a build) | none — a fresh worktree is assumed to run as-is |

`provision` is where the truly project-specific setup lives. It is a pointer, not
a copy: this repo never learns what is in it.

### `ship`

| Key | Means | Default |
|---|---|---|
| `enabled` | may a workflow go past an open pull request? | **`false`** |
| `authorization` | `pre-authorized` or `ask` | **`ask`** |
| `procedure` | the project's own release/deploy document | none |

With `enabled: false` — including when there is no overlay at all — every
workflow **stops at an open pull request**. It does not tag, release, deploy, or
close the issue. Shipping is a property of a project plus your trust in it, never
a property of a procedure.

`enabled: true` with no `procedure` is incoherent: stop and say so rather than
inventing a release ritual.

### `review`

| Key | Means | Default |
|---|---|---|
| `failure_classes` | the doc listing the silent failure modes this repo has actually shipped | falls back to `project.conventions` |

This is deliberately a pointer to a document the *project* maintains. A list of
"what goes silently wrong here" is the least transferable knowledge there is, and
the fastest to rot when it is kept anywhere but next to the code that produces it.

### `docs_move_with_code`

Commands to run when a change alters something a generated document describes —
a code map, an API schema, a CLI reference. Default: none.

## No overlay

Everything above, in one paragraph, for the common case of a repo that has never
heard of this:

Treat the primary checkout as read-only and work in a sibling worktree. Work only
the issue the user named — do not filter a queue by a label you guessed. Claim
nothing. Ask for the test gate rather than inventing one; do not report a branch
as verified without one. Stop at an open pull request: no tag, no release, no
deploy, no closing the issue. Read the README and whatever conventions file
exists, and say plainly which of these defaults you fell back on.

## Worked example

A self-hosted web app that ships from an approved queue:

```yaml
schema: 1

project:
  name: Example App
  conventions: AGENTS.md
  codemap: docs/CODEMAP.md
  primary_checkout: read-only

forge:
  kind: github
  repo: owner/example
  default_branch: main
  branch_prefixes: [feat, fix, perf, chore, docs]

issues:
  approved_label: human-approved
  block_labels: [design-needed]
  claim_label: wip
  severity_labels: [severity:critical, severity:high, severity:medium, severity:low]
  never_set: [human-approved, wip, assignee, milestone]

gate:
  - uv run ruff check .
  - EXAMPLE_ENV=test uv run pytest

worktree:
  root: ../example-<slug>
  provision: docs/agent-workflows/worktrees.md

ship:
  enabled: true
  authorization: pre-authorized
  procedure: docs/agent-workflows/release-and-deploy.md

review:
  failure_classes: AGENTS.md

docs_move_with_code:
  - make map
```

And the whole of a second repo's, which only tracks issues and never ships from
an agent:

```yaml
schema: 1
project: {conventions: CONTRIBUTING.md}
forge: {kind: github, repo: owner/name, default_branch: main}
issues: {approved_label: human-approved, severity_labels: [P0, P1, P2, P3, P4, P5]}
gate: [npm test]
```

Everything else defaults, and the defaults are the safe ones.
