---
name: generating-code-maps
description: Use when a repo's structure gets rediscovered from scratch every session, when an architecture doc or schema inventory has drifted from the code, when onboarding coding agents (Claude Code, Codex, Cursor) to a codebase, or when someone proposes a vector index / RAG layer over source code
---

# Generating Code Maps

## Overview

A map a human maintains goes stale, and a stale map is **worse than no map**: an
agent that finds nothing greps and learns the truth; an agent that finds a
confident wrong answer stops looking. The failure is silent.

**Core principle: derive the map mechanically from the source of truth, and make
staleness a failing test.** No index, no embeddings, no LLM in the read path.
Regenerating is the whole maintenance story.

## When to Use

- Sessions burn their first 10–20 actions rediscovering the same structure
- A doc states counts ("137 tables") that nothing verifies
- Several agent tools are in use and each needs the same orientation
- Someone proposes a vector DB over the codebase — this is the cheaper answer

**Not for:** repos small enough to grep in two calls, or capturing *judgment*
(intent, invariants, why a design is what it is). Judgment goes in a hand-written
file; generators cannot produce it and should not try.

## The one decision that matters

Sort every candidate fact into one of three buckets. Getting this wrong is what
makes the whole thing fail.

| Bucket | Test | Goes in |
|---|---|---|
| Derivable + stable | A script extracts it; same on every machine | The **committed** map |
| Derivable + volatile | Differs per machine or per hour — row counts, sizes, timings | A **gitignored** local file |
| Not derivable | Needs judgment | A **hand-written** file the map links to |

Volatile data in the committed map leaves the guard permanently red, which
teaches the team to ignore it. That is how a guard stops guarding.

## The recipe

This profile already ships a generator:
`~/Development/agent-workflows/scripts/gen_codemap.py`. It maps any checkout
from `git ls-files` (layout, languages, Python symbols, ORM tables, HTTP
routes, tests) and writes `docs/CODEMAP.md`. `setup_repo` offers to run it.
Start there. Extend it in the *project* only for facts this generic pass
cannot see.

1. **Inventory what's derivable** for this stack — [reference.md](reference.md)
   has extraction recipes per language, framework and database.
2. **Write the generator — or use the one that already exists.** Deterministic:
   sort everything, no timestamps, no wall-clock. Enumerate inputs with
   `git ls-files`, never a filesystem walk — otherwise someone's scratch file
   changes the map on their machine alone.
3. **Split the output**: committed skeleton, gitignored volatile file, on-demand
   detail files. Skeleton stays scannable; detail files carry the bulk.
4. **Wire the guard into the gate the repo already runs.** Regenerate in memory,
   compare, fail on diff — with a message that names the fix and distinguishes
   *map behind code* from *your environment behind code*.
5. **Distribute through files already read**: `AGENTS.md`, the Claude
   instructions file, one README line. No install step.

## Attach facts to their subject

Text written *next to* what it describes cannot drift, because changing the thing
means editing the line the text sits on — a comment inside `CREATE TABLE`, a
docstring. Where that's impossible, keep the text in a sidecar keyed by name with
a **hash of the definition** beside it, and report it stale when the hash stops
matching.

If you ship a staleness flag, ship its repair: a refresh that only fills
*missing* entries leaves flagged ones broken forever. Refresh missing **or** stale.

## Match identifiers in context, never by bare name

The highest-value column is *which module writes this, which reads it* — it
answers "where do I go to change this". Anchor matches on `FROM x`,
`INSERT INTO x`, `import x`. Bare-name grep reports every local variable as a
call site, because `listings`, `orders` and `users` are ordinary English, and
then everything looks used.

Then state the limit in the map: empty means **no call site found**, not
"unused" — anything addressed through a runtime-built name is invisible.

## Common mistakes

| Mistake | What happens | Fix |
|---|---|---|
| Counts/sizes in the committed file | Guard red forever, then ignored | Volatile → gitignored |
| Timestamp or commit SHA in output | Diff on every commit | Fingerprint the *inputs* |
| Filesystem walk | Map changes on one machine only | `git ls-files` |
| Bare-name grep | False attribution; everything looks used | Context anchors |
| LLM summarises at read time | Slow, non-deterministic, unverifiable | LLM only *seeds* text, committed + fingerprinted |
| Committing a session-hook config | Runs a command on teammates' machines on pull | Opt-in snippet; pointer in the committed instructions file |
| Guard says only "files differ" | People regenerate against a stale DB and commit worse | Diagnose the cause |

**Expect one failure after a schema change.** If the test suite applies
migrations to a real database, the schema moves during its own run and the first
run after a migration trips the guard once. That is the contract — say so in the
failure message, or it reads as flakiness and gets suppressed.

## Real-world impact

Built for a 122-table repo whose hand-maintained schema page claimed 137 tables
and 42 views — twenty migrations of silent drift in the document people trusted
most. Generation ~1.5 s; committed map ~39 KB read on demand; always-on cost is a
20-line pointer.
