---
name: work-issue-batch
description: >-
  Work through a project's open, approved issues in coherent batches — select 1–3
  related issues, fix them on one shared branch in a worktree, test, open one pull
  request, then (only where the project allows it) release, deploy, verify and
  close the issues, and repeat until the queue is empty or a real blocker is hit.
  Use when asked to continue the issue queue, ship the next batch, work through
  the open issues, clear the backlog, or pick up where a prior batch session left
  off — "keep going", "ship the next batch", "work the queue". This is the
  shipping workflow. Do not use it for a single named issue that should stop at a
  reviewable pull request (that is work-issue), for reviewing someone else's pull
  request, or for filing a new issue.
argument-hint: "[optional: specific issue numbers to take as the first batch]"
display_name: "Work an Issue Batch"
short_description: "Ship batches of approved issues end-to-end until the queue is empty"
wrapper_note: |-
  **Start** in the project's primary checkout — the forge CLI derives the
  repository from the current directory's git remote — but treat that checkout as
  read-only. Each batch gets its own worktree, and every write happens there.

  Whether this workflow may go past an open pull request is the project's call,
  not yours: it is `ship.enabled` in the overlay, and the default is no.
---

# Work approved issues in batches

One batch in, one pull request out — and where the project allows it, one
deployed release and a set of closed issues. Then the next batch, until the queue
is empty or something genuinely needs a human call.

**This document owns only what is different about working several issues as one
unit.** The mechanics of getting a single issue right — hypothesis not spec, read
before editing, the discriminating regression test, verifying in the running
system, docs moving with the code, the commit rules — live in `work-issue.md` and
are not repeated here. Read that file; this one tells you how to select a batch,
how the batch shares a branch, and what happens after the pull request.

## Before anything: read the bindings

`references/project-overlay.md`, then this project's overlay.

Queue: `issue.queue` — open, carrying `issues.approved_label`. If the overlay
names no approval label, **there is no queue**: ask which issues the user means
rather than working every open issue.

**`ship.enabled` decides where this workflow ends.** False, or absent, or no
overlay at all: it ends at an open pull request, exactly like `work-issue`, and
steps 5b–7 below do not run. True with no `ship.procedure`: stop and say so
rather than inventing a release ritual.

## Input

Optionally the user names specific issue numbers. If so, take those as the first
batch instead of auto-selecting. Otherwise pick, using the rules below.

## Authorization

When `ship.authorization` is `pre-authorized`, run the loop without asking per
step: commit, push, release, deploy, close. When it is `ask` — or absent — take
one explicit go-ahead before the first thing that leaves the branch.

Raise a question **up front** only when genuinely blocked: ambiguous scope, a
decision only the repo owner can make, or a destructive action outside this
scope. Otherwise make the reasonable call, note it in the summary, and keep
moving.

## The loop, per batch

### 1. Pick a batch of 1–3 issues

Read each candidate's **full body** (`issue.view`), not just the title, before
selecting.

- Prefer coherent, **same-area** work. A batch that touches one domain reviews as
  one thought; a batch of three unrelated areas is three reviews wearing one hat.
  When both a small same-area cluster and a large feature are open, take the
  small cluster first — not because the large one is deferred, but because it
  ships sooner and leaves a cleaner queue.
- Issues tagged as adversarially verified against the code are higher-confidence
  than untagged ones.
- **A label in `issues.block_labels` means stop** — the shape is deliberately
  open and must not be invented by an agent. Skip it and say so. Unblocking it is
  `clarify-design.md`.
- **Skip anything already carrying `issues.claim_label`.** That is another
  session's claim. Do not strip it to take the issue — a leftover claim from a
  dead session is a human call. Also check remotes and open pull requests per
  `work-issue.md` step 0; the label is the signal, the refs are the backup.

**Size is not a skip reason.** A new module plus a schema plus a job plus an
interface is still in the queue if it is approved and the shape is decided. Take
it as a **batch of one**, or take the already-sliced issues of that same project
together when they review as one thought — do not staple an unrelated small fix
onto a large feature. Do not invent extra scope, and do not pad a large feature
with small fixes so the batch looks "safer".

A multi-day item may outlive one session. That is fine: deliver whatever slice is
actually done and let the next run pick the rest up. Stopping because it looks
big is how a queue fills with approved work nobody touches.

### 2. Claim, then one worktree, one branch, one pull request

As soon as the batch is chosen — before the worktree, and before any edit —
`issue.label-add` the claim label on every issue in it, then `issue.labels-of` to
confirm it took.

Leave the claim on for the whole implementation. Remove it only when the issue is
closed, or when a pull request is opened that links it. Never drop it mid-batch
because the work paused, the session ended, or you moved on to the next issue in
the same batch.

```bash
git worktree add -b <type>/batch-<slug> <worktree.root> origin/<default_branch>
```

Provision it per `worktree.provision`. The batch shares one branch and one pull
request: name the branch for the batch, and put every issue number in the title
and one closing-keyword line per issue in the body.

### 3. Implement each issue

Follow `work-issue.md` steps 2–6 for **each** issue in the batch.

Commit per issue rather than once at the end. A batch that lands as one opaque
commit cannot be reverted issue-by-issue when one of the three turns out wrong.

### 4. Gate before shipping

Run every command in the overlay's `gate`, in order.

**Never ship on red or error-skipped tests.** Not "one unrelated failure" —
establish whether it is yours, and if it is not, say so explicitly and decide
deliberately rather than by momentum.

### 5. Open the pull request

Push and open it per `work-issue.md` step 8. The body already carries a closing
keyword per issue; that is a link, so `issue.label-remove` the claim.

**If `ship.enabled` is not true, stop here** and report. Everything below is the
shipping half.

### 5b. Release and deploy

Follow `ship.procedure` exactly, and nothing else. It is the project's document
because every step in it is a project fact — where the artefact is built, what
pins the deployed version, whether migrations run themselves. Do not improvise
around a step that looks redundant; those documents are usually a list of things
that have each already cost something.

A batch of bug fixes is a patch-level release. A larger bump only for a genuine
feature-level batch.

### 6. Verify against the deployed instance

Per `ship.procedure`. **Say exactly what you verified.** A clean health check
plus a log tail is a different claim from "verified in the interface", and both
should be reported as what they are. Where the deployed system is behind
authentication, an authenticated click-through is the operator's job — an agent
must never type a password into any field.

### 7. Close the issues

`issue.close` with a real comment naming the fix, the release it shipped in, and
how it was verified — not "done". If the claim label is still on the issue (no
linked pull request was opened), remove it here; closing is the other allowed
removal.

### 8. Next batch

Do not stop to write a summary after every batch. Keep going until the queue is
empty or a real blocker is hit.

## Non-negotiables

- Never ship on a red or partially-skipped gate.
- Never edit a migration that has already been applied anywhere — add a new one.
- Never `git add -A`; review `git status` before committing.
- Before anything that could discard uncommitted work, run `git status` first.
- **A seed or system-managed row** — reference data, catalogue entries, anything
  a job rewrites — is read-only in any new interface built for it. Otherwise a
  direct edit is silently clobbered by the next rewrite.
- If a file being touched carries a dense, issue-numbered comment explaining a
  subtle bug it fixed, read the **whole** comment before changing behaviour
  nearby. Those mark real prior incidents.
- Every fix needs a regression test. A test that surprises you while writing it
  means a real bug was found — fix the code, never loosen the assertion.
- Remove the worktree and undo its provisioning when the batch is delivered.

## When genuinely stuck

Ask a short, specific question rather than guessing on: destructive-action scope,
ambiguous product intent with no precedent in the codebase to resolve it, or
credentials and access that are not available. Otherwise decide, document the
decision in the commit message, and continue.
