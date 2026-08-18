---
name: engineering-discipline
description: Use when launching long-running or background work (backtests, sweeps, batch jobs, training), designing a service or production loop, adding CLI flags or environment knobs, setting up logging and progress output, or cutting a release. Covers process detachment recipes, where CPU-heavy work belongs, observability requirements, config precedence, and release discipline.
---

# Engineering discipline

Cross-project operational rules. Project-specific invariants live in
`<project>/.claude/CLAUDE.md` and win over anything here.

## Long-running tasks

- Launch in the background with proper detachment. The reliable POSIX recipe:

  ```bash
  (nohup cmd > out.log 2>&1 < /dev/null &) & disown
  ```

  `setsid` is Linux-only — don't assume it on macOS.
- **Don't use `set -u` with bash functions called via `&`.** The interaction
  between positional args and unbound-variable checks is surprising.
  `set -o pipefail` alone is safer.
- For polling external state the harness can't notify you about, use
  ScheduleWakeup with realistic intervals — 20–30 min for non-urgent checks,
  sub-5-minute only when watching something that genuinely changes that fast.

## Process design

- **CPU-heavy work belongs OUTSIDE production loops.** A live trading or serving
  process should not run model training, large backtests, or other CPU-bound
  batch work on its own host. Compute on a dev or batch machine and sync the
  result file across (rsync or equivalent). This matters most on small or
  single-core production servers.
- Periodic data **refresh** inside the runner (HTTP fetch, file read) is fine.
  Periodic **compute** inside the runner (training, walk-forward, large
  pre-passes) is not, on a small host.

## Observability

- **Every long-running task emits progress with HH:MM:SS timestamps.** That lets
  the operator detect a stall by diffing adjacent log lines. Without timestamps
  a stuck process looks identical to a slow one.
- **Diagnostics must make a post-mortem possible from the files alone** — JSON
  metrics, summary markdown. If a future analysis would need to grep a
  multi-hundred-MB CSV, fix the diagnostics first.
- **At startup, echo the complete resolved config with provenance:** `[cli]`
  (explicitly passed), `[env]` (from an environment variable), `[default]`
  (hardcoded). One log line should tell the operator exactly what configuration
  the run is using.
- Read status from the **source of truth**, not a log tail — one-shot boot
  events scroll out of view.

## Knob design

- **Every CLI flag gets a matching env var.** Precedence is
  **CLI > env > hardcoded default**.
- A bad env value falls through to the default with a warning on stderr. It must
  not crash boot.
- For services, expose env vars for anything ops might tune. Live TUIs and
  dashboards should have a read-only "config" screen showing every resolved
  value and its source.

## Verifying what's actually running

- **Verify the running version and process, not git or `ps`.** An editable
  install needs `pip install -e .` for the version string to update; a pull may
  not have taken; a TUI or dashboard is often a separate process — sometimes on
  a separate host — that an update script never reloaded.
- A dev server left running with `--reload` keeps binding the port, so restarts
  silently fail and routes 404 while the templates look updated. Run
  `--no-reload` and verify the listening PID.

## Resilience & repo hygiene

- Make external and AI-backed features resilient: exponential backoff, honour
  `Retry-After`, degrade gracefully rather than failing the whole run.
- Secrets only in a gitignored `.env`.
- Never `git add` runtime artefact directories (`data/`, `state/`, `logs/`,
  `results/`) — they're gitignored on purpose. Auxiliary debugging scripts you
  create during a session stay untracked and prefixed `_`; delete them once
  they've stopped being useful.

## Releases

**The ritual, in order:** tests fully green → bump the version (patch by
default) → update the CHANGELOG → commit **only the changed files** → tag →
push. Steps vary per project — confirm against `git log` and the project's
CLAUDE.md before starting, especially whether release includes the push and
whether commits carry a `Co-Authored-By` trailer.

- Use the project's release skill or established procedure if one exists. Don't
  improvise the bump / tag / push dance.
- With parallel sessions sharing a git index, commit **pathspec-scoped**
  (`git commit -- <paths>`), never `git add -A`, and verify `git diff --cached`
  before committing.
- **Default to patch bumps.** Minor bumps only on explicit request or a genuine
  breaking change (deleted module, renamed env var, changed audit schema).
- Never release on red or error-skipped tests.
- Don't auto-commit unless explicitly asked — a project's CLAUDE.md may forbid
  it outright.

## Doc-and-code changes at scale

- **A doc-only change at scale should be verified by AST diff before and after.**
  Comments are invisible to the AST, so any surviving delta means logic slipped
  in with the prose.
- Verify code-referencing docs against the live registry — a doc citing a
  symbol that no longer exists is a real bug, not a cosmetic one.
