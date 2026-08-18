---
name: land-prs
description: >-
  Review, sequence, repair, validate, and merge one or more pull requests after
  the user has authorized merging. Use for requests such as "review the remaining
  MRs, fix blockers, and merge", "land these PRs", or "fix this and merge it".
  Optimize the landing order, avoid redundant tests, automatically resolve
  technical blockers, and ask only for genuine product decisions. Do not use it
  for a read-only review (that is review-pr), to implement an issue, or to
  release and deploy.
argument-hint: "[PR numbers or URLs] (defaults to the open PRs the user meant)"
display_name: "Land pull requests"
short_description: "Review, repair, and merge authorized pull requests"
wrapper_note: |-
  **Start** in the project's primary checkout — the forge CLI derives the
  repository from the current directory's git remote — and treat that checkout as
  read-only. Every rebase, repair, test run and app you drive happens in a
  worktree.

  This workflow merges. It does **not** tag, release, or deploy, whatever the
  overlay says about shipping. Merging is not shipping.
---

# Land authorized pull requests

One or more open pull requests in, each one safely on its target, with the
minimum validation that still proves the resulting behaviour.

**This document owns the batch, the repairs, the landing order, and the merge.**
How to review a single pull request — silent failure shapes, attributing a red
test, driving the running system — lives in `review-pr.md` and is not repeated
here. Read that file; this one tells you how to sequence several, what you may
fix without asking, how much to re-run, and how to publish and merge without
losing a commit or landing the wrong tree.

## Before anything: read the bindings

`references/project-overlay.md`, then this project's overlay. The keys that
carry this workflow are `gate`, `worktree.provision`, and
`review.failure_classes`. Then `references/forge-<kind>.md` for the command
behind every operation named below, and `references/worktree-rule.md` before
you create a tree.

No overlay means the conservative defaults: read-only primary checkout, ask
for the gate rather than inventing one, and never report an ungated branch as
verified.

This workflow does **not** read `ship.enabled`. Merging a pull request is not
shipping. Do not tag, release, deploy, or invent a release ritual here.

## Input

The pull requests to land: numbers, URLs, or a phrase such as "the remaining
ones". Take a number out of a URL. If the argument is empty or "remaining",
`pr.open-list` and say which set you took. If nothing resolves, ask rather than
landing the working tree by guess.

## Authority

This workflow runs only when the user has authorized merging. A request such as
"fix the blockers and merge" authorizes:

- Reviewing the requested pull requests.
- Reordering them when that reduces conflicts or duplicate work.
- Repairing technical blockers.
- Updating tests, generated artefacts, and documentation that the repair made
  stale.
- Rebasing or reconstructing a stale source branch.
- Force-pushing **only** with an exact lease bound to the reviewed remote SHA.
- Merging with an exact source-SHA guard.
- Removing a merged source branch when that is already this repository's habit.

It does not authorize deployment, release, production data changes, or
unrelated improvements.

If the user asked for a review only, stop and follow `review-pr.md`. Do not
repair, push, or merge.

## Orient the whole batch first

Inspect every requested pull request before repairing the first one. For each,
`pr.view`, `pr.diff-names`, `pr.fetch-head`, and immediately resolve
`FETCH_HEAD` to a SHA — it is a single shared ref, and the next fetch in the
primary checkout overwrites it.

Record:

- Number, title, linked issue, source branch, exact source SHA, target branch,
  and target SHA.
- Draft, mergeability, approvals, required checks, and labels.
- How far the source is behind its target
  (`git merge-base --is-ancestor <target-sha> <source-sha>`).
- Changed files and affected product surfaces.
- Schema migrations, generated artefacts, shared contracts, and overlapping
  files.
- Explicit and inferred dependencies between the pull requests.
- Whether one has already merged; verify that landing rather than repeating it.

Build a dependency order. A short working table is enough; do not pause for a
plan review.

If the project's conventions require an agent signature, post `review-started`
on each pull request now (`references/agent-signature.md`). This workflow is
`land-prs`.

## Choose the landing sequence

Order the pull requests to minimize repeated rebases, conflict resolution,
database setup, and broad test runs.

Use these priorities:

1. Land required foundations before their consumers: schema, canonical
   contracts, shared helpers, then readers and interface.
2. Respect explicit dependencies and migration order.
3. When two overlap, land the one that establishes the broader canonical
   behaviour first, then adapt the narrower change to it.
4. Prefer an order in which later candidates naturally include all earlier
   merges, so the last tree is the one that needs the full gate.
5. Among independent pull requests, prefer the order that reuses setup and
   validation evidence most effectively.
6. Never violate a semantic dependency merely to save test time.

Landing is serial because every merge advances the target. Recalculate the
remaining order after each merge.

Tell the user the chosen sequence and any important assumption. Do not request
approval unless the sequence itself changes product behaviour.

## Review and repair each pull request

For each, follow `review-pr.md` against the original source SHA and its stated
target: read the linked issue, hunt the failure classes in
`review.failure_classes`, reproduce important claims through the production
entry point, and attribute any red test with a second worktree rather than a
stash.

Then repair, in a worktree of your own:

1. Fetch again and confirm the remote source SHA is still the SHA you reviewed.
   If it moved, inspect the new commits and incorporate them; never overwrite
   them blindly.
2. Create the repair worktree. Prefer the existing source branch, cut from
   the latest target only if that branch is already checked out elsewhere:
   ```bash
   git worktree add ../<repo>-land-<N> <source-branch>
   ```
   Provision it per `worktree.provision`.
3. Reconstruct the pull request's intended delta onto the latest target —
   rebase, cherry-pick, or replay — using the smallest approach that
   produces a clean, reviewable result. Keep the existing source branch
   name; a new branch for the same pull request is a last resort.
4. Fix technical blockers automatically (see below).
5. Keep documentation, generated artefacts, and tests synchronized with the
   repaired behaviour. Run everything in `docs_move_with_code` when a
   structural surface moved.

Stay inside the requested pull request's intent. Do not smuggle unrelated
cleanup into it.

## Fix automatically versus ask

Fix without asking when repository evidence determines the answer, including:

- Stale-base conflicts.
- Migration-number collisions.
- Generated-file drift, including anything `docs_move_with_code` regenerates.
- Documentation and test expectations made stale by an already-landed contract.
- Mechanical API, import, type, route, or naming integration.
- Missing regression coverage for a repair you just made.
- Clear correctness, safety, or performance bugs whose intended behaviour is
  already specified — in the issue, the conventions, or the target branch.
- Conflicts where the target branch establishes the current canonical
  convention.

Ask only when multiple materially different product outcomes remain valid,
including:

- The business meaning of a metric or classification.
- Conflicting acceptance criteria.
- A user-visible workflow with more than one plausible behaviour.
- A choice that changes canonical identity, ownership, or data retention.
- Destructive or irreversible data treatment.
- A material scope, privacy, cost, or security tradeoff.

When a decision is needed, give the evidence, two or three concrete options,
and their consequences. Pause only the affected dependency chain; continue
independent pull requests when doing so cannot bias the decision.

Do not ask whether to perform an ordinary technical repair.

## Validate proportionally

Derive validation from the changed behaviour rather than running every
available suite by habit. The overlay's `gate` is the project's required
check, not a licence to skip it and not a requirement to re-run it after
every already-tested merge.

For each pull request, identify:

- Directly changed modules and surfaces.
- Callers and contracts affected by the change.
- Existing tests covering those symbols or routes.
- The regression test that proves each repair.
- Data, interface, migration, or performance evidence the claims actually
  need.

Use the narrowest sufficient ladder:

1. Syntax, static, or generated-artefact checks the diff directly affects.
2. Focused unit and contract tests for changed code and immediate consumers.
3. Migration and data checks on a realistic disposable database when data
   behaviour changed.
4. Live interface validation for routes, templates, forms, navigation, or
   charts — from this worktree, on its own port, against its own data.
5. Representative timing or plan checks only for performance claims.
6. The full overlay `gate` when the blast radius is shared infrastructure,
   authentication, a destructive migration, a core data invariant, or
   behaviour you cannot isolate confidently.

Otherwise run focused validation per pull request, and the full `gate` once
on the final candidate after it has been rebased onto every earlier merge.
That validates the resulting target tree without repeating the same expensive
suite for every independent pull request.

Rerun only what a repair or rebase invalidated. Do not rerun an unchanged
suite merely because the already-tested commit was merged.

If the overlay names no gate, find the project's own test command and confirm
it with the user before pushing. Never report an ungated branch as verified.

If a test fails:

- Determine whether the failure is caused by this pull request.
- Compare with the untouched current target when attribution is unclear
  (`review-pr.md`).
- Fix branch regressions automatically.
- Do not hide a required red check, and do not describe limited validation as
  a full pass.

A successful request or a raw query is not proof that the surface works.

## Publish the repaired branch

Before rewriting a source branch:

1. Fetch again.
2. Confirm its remote SHA still equals the SHA originally reviewed (or the
   SHA you already incorporated).
3. If it moved, stop and incorporate the new commits; never overwrite them.
4. Push with an exact lease bound to that reviewed remote SHA:

   ```bash
   git push --force-with-lease=refs/heads/<branch>:<reviewed-remote-sha> origin <branch>
   ```

   Bare `--force-with-lease` is not exact: a fetch updates the remote-tracking
   ref and the lease then protects nothing. Never `--force`.

Confirm the push by comparing refs, not by reading the command's output.

Update the pull request body with `pr.update-body` so it truthfully records
the final behaviour, the repairs made during review, relevant migrations or
documentation, the exact validation performed, and any limitation or
unavailable remote check. Write the body to a file first.

Wait for `pr.checks` on the exact pushed SHA. Required checks that have not
run are not a pass.

If the project's conventions require an agent signature, post `reviewed-pr`
on the pull request and on the linked issue once that review-and-repair has
actually concluded — not before.

## Merge

Immediately before merging, verify the tested tuple:

- Target SHA.
- Source SHA.
- Source tree (`git rev-parse <source-sha>^{tree}`).
- Required check state on that source SHA.

The target must be an ancestor of the source
(`git merge-base --is-ancestor <target-sha> <source-sha>`). If the source or
the target moved, rebase or re-evaluate and rerun only the validation that
movement invalidated.

Merge with `pr.merge` and an exact source-SHA guard. Never omit the guard.
Use the merge method this repository already uses — look at recent merges on
the default branch; do not invent one. Delete the source branch only when
that is already this repository's habit. Do not bypass required checks.

Never treat a successful command message as proof. After merging:

1. Fetch the target.
2. `pr.view` and confirm it is merged.
3. Confirm the landing tree matches the tested source tree.
4. Confirm the linked issue closed when the pull request promised to close
   it. If it did not, say so; do not close it by hand. Closing by keyword on
   merge is the mechanism; this workflow does not ship.
5. If the project's conventions require an agent signature, post `merged-pr`
   on the pull request and on the linked issue.
6. Remove only the worktrees and branches this landing created, and undo
   their provisioning.
7. Use the new target SHA as the baseline for the next pull request.

## Completion report

`references/recap.md` carries who the reader is, the readability contract and
the one hard rule. Read it. What follows is only this workflow's required
shape.

Report:

- The actual merge order.
- Each pull request's final source SHA and merge commit.
- Technical blockers repaired.
- Validation performed, distinguishing focused, full gate, interface, data,
  and remote-check evidence.
- Linked issue status.
- Any pull request left open and the exact product decision blocking it.

Do not call the batch complete until every requested pull request is merged,
already verified as merged, or explicitly blocked by a genuine product
decision.
