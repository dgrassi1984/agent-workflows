---
name: web-data-engineering
description: Use when building or debugging a server-rendered web app — HTMX or similar partial-swap frontends, Jinja/template rendering, SQLite-backed apps, Chart.js or canvas charts, background job status tracking, or .env-driven config. Covers the silent failure classes behind "the widget vanished", "nothing happens when I click", "the page hangs", "the toast never appeared", and stale-config bugs.
---

# Web & data app engineering

Generic mechanisms, learned the hard way. A project's own CLAUDE.md may pin
specific helpers and file locations — those win over anything here.

## HTMX and partial swaps

- **`hx-boost` is inherited.** Child forms, tiles and selects inherit the body's
  `hx-target` / `hx-select`. A fragment response that doesn't contain the
  selected element swaps in *nothing* — this is the real cause of "the widget
  vanished" and "the page went blank". Set an explicit `hx-target` and an
  explicit `hx-select` (a real selector, or unset it) on every element that
  loads a partial.
- **Fragment swaps don't reliably execute inline `<script>`.** Use a declarative
  hook the app already re-runs after settle instead of inline script.
- **Re-executed inline scripts with a top-level `const` throw "already
  declared" and halt silently** — everything after that line in the script
  never runs, with no visible error.
- **Every page script can run TWICE per boosted arrival** if the app also
  re-runs scripts after settle. An IIFE only prevents the redeclaration crash;
  it does not prevent double binding. Bind listeners through a
  bind-once helper keyed by element and event, and make bootstraps one-shot —
  otherwise one click does its work twice.
- **`htmx:afterSettle` does NOT fire on Back/Forward.** History restore fires
  `htmx:historyRestore` instead, so any cleanup or re-init must bind both.
- **A bare `setInterval` with no teardown survives boosted navigation** and
  races the next swap.
- **An `HX-Redirect` destroys the DOM that its own `HX-Trigger` toast was just
  built in** — the confirmation vanishes exactly when the user most needs it,
  and they land on a different page with no explanation. Stash the message
  (e.g. in `sessionStorage`) and drain it on the next load.
- **Never send a 3xx to an HTMX form.** It gets followed and a whole page is
  swapped into a fragment-sized target.

## SQLite

- **WAL readers do not sail past a heavy writer.** `mode=ro` readers still
  contend with the single write lock, so a click can hang for the entire
  multi-minute duration of a writer — this is the real "nothing happens" cause.
  Configure WAL and `busy_timeout` everywhere; concurrent write-heavy runs
  deadlock on the write lock.
- **`PRAGMA analysis_limit=N` (N>0) is not a cheap approximation of ANALYZE — it
  CAPS every recorded rows-per-distinct-value at N+1.** The columns it
  misreports are precisely the non-selective ones, so the planner is told they
  are the *most* selective in the schema (a match covering 93% of a table
  recorded as ~1000 rows). Raising N only rescales the error; **only `0` is
  correct.** Fresh, present statistics can still be wrong for this reason alone
  — check `sqlite_stat1` for values exactly equal to the bound + 1.
- **Don't key a cache on whole-DB file mtime** — any write anywhere busts it.
  Key narrowly and warm it on a startup hook.
- Watch for bad join orders full-scanning million-row tables.
- **SQLite doesn't shrink on delete** (`auto_vacuum=0` plus an empty freelist).
  Diagnose "bloat" by table and index size, never by file size.

## Charts

- **`maintainAspectRatio:false` with no fixed-height parent enters an infinite
  resize loop that hangs the page.** Wrap every canvas in a fixed-height
  container. No-data fallbacks must hide the wrapper, not just the canvas.
- **Chart.js keys its registry by canvas ELEMENT.** After a partial swap
  replaces the DOM, `Chart.getChart(newCanvas)` returns `undefined` and the old
  chart is orphaned — a hand-copied per-template guard silently misses it.
  Centralise creation and destruction in one helper with an **id-keyed**
  registry plus an after-settle sweep, and pin that with a test so templates
  can't drift back to constructing charts directly.

## Background jobs and status

- **A `status='running'` row cannot prove its own liveness.** The final UPDATE
  lives inside the worker's own try/except, so a SIGKILL, OOM or restart leaves
  the row claiming to be in flight for ever — and a "you can't touch a running
  job" guard then makes the corpse permanently undeletable, which is worse than
  a wrong label.
  - Stamp the owning process's **complete identity**: pid + host + the
    OS-reported process start time. A bare pid reads as alive again once a
    reboot recycles it.
  - **An age cutoff cannot distinguish a dead run from a slow one** — it either
    kills a long backfill or lies for hours. Ask the OS.
  - A failed or ambiguous process probe is **UNKNOWN, never dead**, and a
    partial identity must take the guarded identity-less path.
  - Register every new run-tracking table with the reaper. Two independently
    correct, mutually unreusable reconcile functions is how a third table ends
    up with no reaper at all.
- **Never rely on a final UPDATE to repair a false reap** — an `interrupted`
  state usually exposes a Delete control, and deleting a live parent breaks its
  worker's next child insert.

## Soft deletes and tombstones

**Turning a DELETE into a tombstone re-points every "is this still referenced?"
sweep at the tombstone.** Recording a removal instead of erasing it is usually
right — it's what stops a system re-proposing something a human already
rejected — but the row it leaves behind is still a row. Any reflection-based
sweep asking "does anything reference this?" now answers *yes*, so the cleanup
permanently protects exactly what it was pressed to remove.

When a cleanup stops deleting, re-read every consumer that counts rows in the
table it writes to and make each ask its **own** question, not a generic "did a
human decide anything here?". A soft delete is also invisible to FK
`ON DELETE CASCADE`, and it surfaces only after somebody presses the button —
which is why the control run shows nothing.

## Config, templates and refactors

- **`.env` precedence:** make it authoritative with `load_dotenv(override=True)`
  through ONE loader at the entrypoints, or a stale systemd `Environment=` line
  or a shell export will silently shadow it. But `load_dotenv()` at import time
  leaks `.env` into pytest — strip env-driven config in `conftest.py`.
- **Harden templates with `.get()`** rather than direct key access.
- **On any column drop/rename or unpack-pattern refactor, sweep ALL writers,
  callers and templates** — dynamic SET clauses, rare branches, and one missed
  destructure will pass type checks and blow up at runtime. After a big rewrite,
  grep for orphaned helpers and confirm each periodic write still fires.
- **Diagnose display-vs-data first.** A raw ISO date rendered in an
  `en`-formatted UI only *looks* like swapped day and month.
- **Don't feed mutable numeric scores into LLM prompts** that generate stored
  prose — the model quotes them, they persist, and they go stale and contradict
  the live-recomputed value on screen. Feed direction and context, not raw
  relative scores with no direction, or the prose invents optimism the UI
  contradicts.
