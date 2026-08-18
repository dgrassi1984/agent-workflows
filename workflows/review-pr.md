---
name: review-pr
description: >-
  Review a pull request before it lands — check it out into a detached worktree,
  hunt the silent failure classes this codebase actually ships, re-run and verify
  the claims the description makes, drive the affected surfaces in the running
  system, attribute any failing test to the branch or to the default branch, and
  report blocking findings. Use whenever the user points at a pull request and
  wants it reviewed, checked, or assessed before merge — "review PR 556", "is
  this safe to merge?", a bare pull-request URL, or a request to look over
  someone else's branch. Also use it before merging work an agent produced in
  another session. Do not use it to implement an issue, to file a new issue, or
  to release and deploy.
argument-hint: "[PR number or URL] (defaults to the PR for the current branch)"
display_name: "Review a PR"
short_description: "Hunt this repo's silent failures in a PR before it lands"
wrapper_note: |-
  **Start** in the project's primary checkout — the forge CLI derives the
  repository from the current directory's git remote — and read the diff there.
  To run anything (the gate, the app, a query), take the branch out into a
  **detached** worktree first. Never `checkout`, `stash` or `checkout <ref> -- .`
  in the primary checkout itself: parallel sessions are reading those files.

  Merge only when explicitly asked.
---

# Review a pull request

Review the pull request identified by the argument. If it is empty, resolve it
from the current branch (`pr.for-current-branch`) and say which one you picked.
If it is a URL, take the number from it. If nothing resolves, ask rather than
reviewing the working tree by guess.

## Before anything: read the bindings

`references/project-overlay.md`, then this project's overlay. Three keys carry
this workflow: `gate` (what you re-run), `worktree.provision` (what a fresh tree
still needs), and **`review.failure_classes`** — the document where this project
records what goes silently wrong in it. Read that document in full before reading
the diff. Then `references/forge-<kind>.md` for the commands.

## Why this is not a style review

The failures worth catching are almost never crashes. They are **silent**: a
number that looks right and is wrong, a surface that renders empty instead of
erroring, a job that records success having done nothing, a rule that was never
compiled. A diff can be clean, tested and documented and still ship one of these.

Review less for whether the code is good, and more for what it makes the system
tell its users — and whether that is true.

## Orient before reading the diff

`pr.view`, `pr.diff-names`, then `pr.fetch-head` — and immediately resolve it:

```bash
git rev-parse FETCH_HEAD                         # write this SHA down
git diff --stat origin/<default_branch>...<SHA>
```

`FETCH_HEAD` is a single shared ref: the next session to fetch in the primary
checkout overwrites it, and your later commands then silently describe their
branch. Resolve it to a SHA once, at the top, and use that SHA from then on.

If the project's conventions require an agent signature, post `review-started`
on the pull request now (`references/agent-signature.md`). This workflow is
`review-pr`.

Reading the diff is all you may do in the primary checkout. To run anything, take
the branch out into a worktree of your own. A review needs no branch, so detach:

```bash
git worktree add --detach ../<repo>-review<N> <SHA>
```

Then provision it per `worktree.provision`. **Provisioning is not optional for a
review**: several of the failure shapes below are invisible against a
half-configured tree, and two of them look exactly like a bug the branch does not
have.

Establish two things before judging anything:

- **Is the default branch already red?** Establish this first, or you will spend
  the review chasing a failure the branch did not cause. Attribute it with the
  procedure below.
- **Is the branch current?**
  `git merge-base --is-ancestor origin/<default_branch> <SHA>`. If it is not an
  ancestor, the branch is stale and the diff is not what will land.

## Silent failure shapes

These are the *shapes*. Which of them this codebase has actually shipped, and in
what form, is in `review.failure_classes` — read there for the instances, and
treat that document as the authority. A shape with no instance recorded is still
worth a look; an instance recorded there is worth a search.

- **An authorization check that is missing rather than wrong.** A handler that
  parses an id from input and loads the row without confirming it belongs to the
  caller is a cross-user data leak, and it looks exactly like every correct
  handler around it. Check every new entry point that takes an id.
- **A generated build product that is stale.** Anything compiled at package time
  and ignored in the repository is stale or absent in a fresh tree, and the parts
  of it that are new to the repo simply do not exist — no error, no missing file.
  Rebuild before judging any rendered surface, and confirm a suspected geometry
  problem by measuring geometry, not by looking at a screenshot.
- **A migration edited after it was applied somewhere.** Databases stamped as
  having run it never re-run it, so the columns never appear while the models
  select them — and continuous integration usually cannot catch it, because it
  builds from the models or replays onto a fresh database where the edited file
  is self-consistent. If the diff modifies an existing migration, that is blocking
  unless it demonstrably never left one machine.
- **A number that quietly changes meaning.** A new path that skips a conversion
  or a validator turns a plausible number into a wrong one with no error.
  Widening a set is often correct and still needs saying: if a query starts
  including a new account, currency or category, any surface labelling that total
  is now lying unless it was relabelled in the same commit.
- **A surface that goes blank instead of saying why.** For anything that removes
  or repoints a data source, find its readers and ask what they render when it
  returns nothing. Distinguish "we know there is nothing" from "we do not know" —
  both render as an empty list unless someone makes them different, and an
  unlabelled blank where the honest answer is "not loaded yet" is a defect. **A
  silent empty result is a bug**, usually a swallowed error.
- **A job that reports success having done nothing.** Check what it anchors its
  next run on, what it does with a rate limit or a partial failure, and whether
  an "is it running?" flag read from an open row survives the process dying.
- **A convention hand-rolled instead of imported.** Where the codebase has a
  shared macro, helper or component for a behaviour, a diff that reimplements it
  locally will drift from it. Some projects fail the build on this; most do not.

## Verify the description's claims

Do not accept them. Descriptions list tests run and counts observed. Re-run the
overlay's `gate` from your worktree — the gap between "21 passed" in a description
and 21 passing locally is where reviews earn their keep.

If the description claims a stored count, reproduce it **through the production
entry point** — the function the route calls, the surface as it renders. A
`COUNT(*)`, a command-line verb or a lower-level helper measures something
adjacent to the claim, and this is exactly how a careful, honest measurement
becomes a wrong number that then becomes somebody's acceptance criteria.

## Attribute a failing test with worktrees, never with `git stash`

Stashing and `git checkout <ref> -- .` answer the question by rewriting the
working tree under every other session reading it, twice, and a `stash pop` that
conflicts leaves the tree in a state nobody asked for.

```bash
# 1. as reviewed — the branch commit plus any fix you are trying
cd ../<repo>-review<N> && <gate for the one failing test>

# 2. the default branch alone — `git worktree` works from any worktree
git worktree add --detach ../<repo>-review<N>-base origin/<default_branch>
cd ../<repo>-review<N>-base && <the same command>
```

Only the second distinguishes "the branch broke it" from "the default branch is
already red". Report which, then remove the extra tree and undo its provisioning.

## Verify in the running system

Tests passing is not the same as the surface being right, and several shapes
above are invisible to any suite. Run from the review worktree **on its own port
against its own data**, and check the port belongs to the tree you think it does.
Inspect what actually renders, including the empty case.

## Report

`references/recap.md` carries who the reader is, the readability contract and the
one hard rule. Read it. Roughly 500–800 words unless the pull request genuinely
needs more.

1. **Decision** — approve, request changes, or blocked.
2. **What the PR is meant to fix** — the original user-visible problem and the
   expected behaviour, in a few sentences.
3. **What it changes and what works** — the approach, material trade-offs, and
   the verified happy path.
4. **Blocking problems and proposed fixes** — for each, a concrete scenario, the
   product or operational impact, and the smallest viable fix. Include enough of a
   repair plan that a follow-up can be scoped without reconstructing the review.
5. **Worth knowing / out of scope** — non-blocking and pre-existing issues, kept
   brief and clearly separated.
6. **Validation** — exact test, data and interface results, including limitations
   and any pre-existing failures on the default branch.
7. **Bottom line** — what should happen before merge.

Classify every finding:

- **Blocking** — ships a wrong number, blanks a surface, leaks another user's
  data, creates false success, or can stop a job.
- **Worth knowing** — true but not blocking: an unexercised guard, a widened
  scope, a pre-existing red test.
- **Out of scope** — a real problem the branch did not introduce and should not
  be blocked on.

If you fix something, add a regression test that fails without it, and **prove**
it goes red rather than asserting it. If the user authorizes only some findings,
change only those and preserve the rest in the handoff rather than silently
treating them as resolved.

If the project's conventions require an agent signature, post `reviewed-pr` on
the pull request and on the linked issue (`references/agent-signature.md`)
once the review has actually concluded — not before.

## Merging

Merge only when asked. Then remove the review worktrees and undo their
provisioning — each one left behind holds a checkout and whatever the
provisioning step created.

If the default branch is red for unrelated reasons, say so in the report rather
than quietly merging onto red. That is the operator's call.
