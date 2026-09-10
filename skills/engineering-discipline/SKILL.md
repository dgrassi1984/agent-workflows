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
- For validation, use the shared `workflow_run.py` helper described in
  `~/Development/agent-workflows/references/validation-policy.md`. It serializes
  heavy validation across projects, includes queue/provision/retries in the
  budget, writes raw logs to disk and emits stage changes. Use its bounded
  watcher or the tool's completion notification, not repeated model-driven
  sleeps and unchanged log tails. Keep required user progress updates concise.
- Queue heavy builds, renderer checks and benchmarks through the same host slot.
  Lightweight inspection can run in parallel. Do not pause or change unrelated
  active jobs without authorization. A baseline investigation should run the
  failing scenario first, not start another complete suite by habit.
- For external state, use the available scheduled-task/notification capability
  only when the user requested monitoring. Select intervals appropriate to the
  event; do not invent an unavailable scheduling API.

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
- Return the verdict, a bounded relevant failure excerpt, and artifact paths.
  Filter output before returning it; keep full logs on disk. Read source ranges
  or diffs. Reuse applicable skill instructions after their first read unless
  the source changes. Mandatory tool instructions still need to be read.

## Knob design

- Add environment overrides when deployment or operators need them. For
  workflow commands and audit-sensitive policy, prefer explicit CLI arguments
  and the project overlay; avoid a second hidden configuration channel. Where
  both exist, precedence is **CLI > env > configured default**.
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

Cutting a version is a procedure, not a habit: follow
`~/Development/agent-workflows/workflows/release.md`.
The overlay's `ship.enabled` / `ship.versioning` / `ship.procedure` are the
bindings. Do not improvise a bump / tag / push dance, and do not copy one
into a project document.

- Follow `ship.release_cadence`; merge completion does not always require a new
  version. Preserve pending merges for the next release checkpoint.
- Keep assertion failures, infrastructure failures and authorized timeout
  waivers distinct. Never report waived validation as passed.
- Commit **pathspec-scoped** (`git commit -- <paths>`), never `git add -A`.
- Verify the **running** version after deploy, not git or `ps`.
- Don't auto-commit unless the overlay's authorization (or the user) said to.

## Doc-and-code changes at scale

- **A doc-only change at scale should be verified by AST diff before and after.**
  Comments are invisible to the AST, so any surviving delta means logic slipped
  in with the prose.
- Verify code-referencing docs against the live registry — a doc citing a
  symbol that no longer exists is a real bug, not a cosmetic one.
