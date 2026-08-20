---
name: work-issue
description: >-
  Take one tracked issue (number, URL, or description), implement it end-to-end
  on a dedicated branch cut from the default branch in its own worktree, verify
  it in the real running system, move the docs with the code, then push and open
  a pull request. Use this whenever the user points at a single issue and wants
  it worked on, fixed, implemented or delivered — "work on #397", "do issue 412",
  "implement this and open a PR", a bare issue URL, or any request to turn one
  tracked issue into a reviewable branch. Also use it when the user describes a
  bug that already has an issue, or asks for a fix delivered as a PR rather than
  as a direct commit. Do not use it for read-only questions about an issue ("what
  does #397 say?", "summarise the open issues"), for reviewing or landing a PR
  someone else opened, for working several issues as one shipped batch, or for
  the release ritual — those are different jobs with their own workflows.
argument-hint: "[issue number, URL, or description]"
display_name: "Work an Issue"
short_description: "Take one issue to a verified, reviewable pull request"
wrapper_note: |-
  **Start** in the project's primary checkout — the forge CLI derives the
  repository from the current directory's git remote — but treat that checkout
  as read-only. The procedure moves you into a dedicated worktree at step 1, and
  every write after that — edits, tests, the app you drive, the commit, the push
  — happens there.

  This workflow stops at an open pull request. It does **not** bump a version,
  tag, deploy, or close the issue, whatever the overlay says about shipping.
---

# Work one tracked issue into a pull request

One issue in, one reviewable branch and pull request out. The value is not the
diff — it is that the diff is *correct, complete, verified, and documented*
before a human is asked to look at it.

## Before anything: read the bindings

1. `references/project-overlay.md` — then read this project's overlay. It names
   the forge, the labels, the gate, the branch prefixes, and whether the primary
   checkout is shared.
2. The project's `conventions` document. **Its conventions win over any generic
   habit, and its gotchas are the failure modes this repo has actually hit.**
3. `references/forge-<kind>.md` for the command behind every forge operation
   named below in `code font`.

No overlay means the conservative defaults, and they are not a licence to guess:
work only the issue you were given, assign it to the logged-in forge user, and
ask for the gate.

## Input

The issue reference: a number, a URL, or a description to resolve to one. If it
is a description, `issue.search` first and confirm the match before starting. If
nothing matches, say so and ask — do not invent an issue number.

## 0. Ground yourself before touching anything

`issue.view` and `issue.view-comments`, then `git fetch origin`.

Read the **whole body**, not the title. Later comments often revise it. If the
issue is already closed, or already has a pull request, say so and confirm before
building anything — you may be looking at work that is already done.

**Check nothing else is already on it.** Where the overlay names a
`issues.claim_label`, that label is the claim: if the issue already has it, stop
and say so — do not strip it to take the work. Leftover claim from a dead session
is a human call. Two other places give a claim away even if the label was missed,
and they are the only check you have when the project has no claim label at all:

```bash
git ls-remote --heads origin | grep -i "<issue-number>\|<distinctive-noun>"
```

plus `pr.search` for the issue number. Branches carry the issue number on the end
for exactly this reason.

**Note the labels.** A label in `issues.block_labels` means the shape is
deliberately open and must not be invented by an agent — stop, and say which
decision is missing. The `issues.approved_label` means it is cleared to build.
Something with neither is not forbidden, but say which you are working on.

## 1. Branch — in a worktree of your own, never in the shared checkout

`references/worktree-rule.md` is the canonical procedure and explains why; the
short version is that the primary checkout's branch, index and files all move
under you while you work, so a commit made there can land on another session's
branch and a push can report success having delivered nothing.

```bash
git worktree add -b <type>/<slug>-<N> <worktree.root> origin/<default_branch>
```

Then provision it from the doc `worktree.provision` names. Every item on such a
list is there because skipping it fails *quietly*.

Claim the issue as soon as the worktree exists, before any edit.
`issue.assignee-add` the logged-in forge user, then `issue.view` to confirm it
took. If the overlay names a claim label, `issue.label-add` that too, then
`issue.labels-of` to confirm. Leave both on for the whole implementation.
Remove them only when a pull request is opened that links the issue, or if the
issue is closed without one. This workflow stops at an open pull request, so
the removal is step 8. Assign even when there is no claim label, and even if a
leftover overlay still lists `assignee` under `never_set`. If assignment did
not take, say so and continue. If the project's conventions require an agent
signature, post `started-work` on the issue now
(`references/agent-signature.md`).

**Everything from here — edits, tests, the app you drive, the commit, the push —
happens in that worktree.**

## 2. Treat the issue's diagnosis as a hypothesis, not a spec

This is where most of the value is won or lost. Issues are written by someone
reasoning about the code, often correctly about the *symptom* and only partly
about the *cause*. Before implementing the proposed fix, confirm the mechanism
yourself — read the actual code paths, and where you can, reproduce the failure.

Then check three things the issue probably did not:

- **Is the stated scope complete?** An issue that lists "5 templates / 6 call
  sites" is reporting what its author found. Enumerate the whole class yourself
  and expect a different number.
- **Would the proposed fix actually fix it?** If your reproduction shows the
  suggested remedy addresses only one of several failure modes, say so plainly in
  the pull request and fix the real thing. Being right matters more than matching
  the ticket.
- **What was the broken behaviour masking?** A crash, an early return or a
  swallowed error can be *suppressing* other bugs. When you remove it, that
  suppressed code starts running. Re-measure the surrounding behaviour after your
  fix and compare against before.

## 3. Implement

**Read 30–100 lines around every edit site before touching it.** Most
edit-introduced bugs come from missing context in the function above or below.

**Copy the closest existing pattern.** A codebase with strong conventions — an
add/edit/delete flow, a settings tab, a chart, a modal, a bulk-select surface —
is telling you what to write. Matching it is not optional polish; it is what
keeps the codebase legible. The `conventions` doc lists the load-bearing idioms
and `project.codemap`, where there is one, says where things are.

Fix the class, not the instance. If the same mistake appears in N places, change
all N and remove the pattern that let them drift. Delete the now-dead local
variants rather than leaving them beside the shared one.

Keep the scope the issue asked for. Real problems you find outside it go in the
pull request description as follow-ups, not into this branch.

If a file you are touching already carries a dense, issue-numbered comment
explaining a subtle bug it fixed, **read the whole comment** before changing
behaviour nearby. Those mark real prior incidents, not decoration.

As you go, keep a running note of every fork in the road you actually hit: what
you chose, what else was on the table, and why. The report needs these verbatim,
and reconstructing them afterwards produces decisions that read as deliberate but
weren't.

### If you touch the schema

Tool-neutral, and true wherever migrations exist:

- **A model change needs a migration.** Projects that check model-to-migration
  drift will fail the build without one; projects that do not will fail at
  runtime instead, which is worse.
- **Validate the migration up AND down.**
- **Never edit a migration that has already been applied anywhere** — a
  long-lived local database or a deployed one. Those are stamped as having run
  it, so re-running is a no-op and the new columns never appear while the models
  select them. Continuous integration usually **cannot** catch this: it builds
  the schema from the models, or replays migrations onto a *fresh* database where
  the edited file is self-consistent. Nothing replays a previously-stamped state.
  The repair is forward-only: a new migration that adds the column if it is
  missing.
- **A column drop or rename means sweeping all writers, callers and templates**,
  including dynamically built statements and anything string-interpolated, where
  no compiler or linter will find them for you.

## 4. Pair the fix with a regression test that discriminates

Write a test that fails loudly if the bug returns, named for the issue so a
future reader knows why it exists. State in the docstring what reverting the fix
breaks.

Then **prove the test can fail.** Reintroduce the bug temporarily and confirm it
goes red, and confirm it does not fire on lookalikes that are actually fine. A
guard that has never failed is a guard you have not tested. Where the broken
state is invisible from reading the code — a unit mismatch, an off-by-one, a
silent zero — assert against it explicitly (`assert real_pnl != 0.0` where the
bug always produced 0).

If the test surprises you by catching something you did not anticipate, that is a
**bug found** — fix the code, never loosen the assertion.

When you change behaviour, find the tests pinning the *old* behaviour. A test
that silently keeps passing on changed code means you missed a callsite.

## 5. Verify in the real running system

Reading the diff is not verification. Drive the actual system through the steps
the issue describes, plus the neighbouring surfaces the change touches. Observe
what *renders* or what the process actually emitted, check for errors the happy
path hides, and prefer a measurement over an impression.

Run it **from your worktree, on its own port, against its own data**. A page
fetched from another session's server shows their branch while looking exactly
like proof of yours.

If the project builds assets, **rebuild them before judging anything visual**. A
build product that is generated at package time and ignored in the repository is
stale or absent in a fresh worktree, and a rule that was never compiled does
nothing at all — no error, no missing file. Bust any cache with a random query
parameter rather than a version string that has not changed, and confirm a
suspected geometry problem by measuring the geometry rather than by looking at a
screenshot.

**A silent empty result is a bug**, not a pass — zero rows added, a link that
does nothing, usually a swallowed error. Root-cause it.

Then run the overlay's `gate`, every command, in order. If something fails,
establish whether it is *yours* before reporting it as pre-existing:

```bash
git diff --name-only origin/<default_branch>
git stash list                           # nothing of yours should be parked
```

If the overlay names no gate, find the project's own test command and confirm it
with the user. Never report an ungated branch as verified.

## 6. Docs move with the code — in the same commit

Do this before committing, never "at release time".

1. **Run everything in `docs_move_with_code`** after a structural change — a new
   module, route, table, job or configuration key. Generated documents are
   usually guarded in continuous integration, and they are generated, so never
   hand-edit one.
2. **The `conventions` doc**, when you learned something a future session would
   otherwise rediscover the hard way — a non-obvious failure mode, a new
   convention your change introduced. Symptom, cause, rule. No counts, no
   inventories: those are what drift.
3. **The procedure docs**, if you changed how the work itself is done.
4. **Any doc you found contradicting the code**, even one your change did not
   touch. The code wins; fix the doc in this same commit.

**Do not touch a changelog or a version.** Those belong to the project's release
procedure, which this workflow does not perform. What you write in your *commit
body* is the raw material for it.

State the docs outcome explicitly in your report — the files you touched, or
"docs: none — no documented surface changed". Silence is how drift starts.

## 7. Commit

```bash
git rev-parse --abbrev-ref HEAD          # confirm you are where you think you are
git add -- <new files only>
git commit -F <message-file> -- <explicit paths>
git diff --cached                        # look before you commit
```

- **Never `git add -A` or `git commit -a`.** A blanket add sweeps in whatever
  driving the system left behind in the tree.
- Options go **before** the `--`; everything after it is a pathspec.
- Subject: what changed and why, plus the issue number.
- Body: the real story — the mechanism you found, where the issue's diagnosis was
  incomplete, what you measured before and after, what you deliberately left out
  and why, the test result, and the docs line.
- Trailer: `Co-Authored-By: <assistant> <model> <noreply@…>`, naming the model
  actually doing the work.

## 8. Push and open the pull request

```bash
git fetch origin
git merge-base --is-ancestor origin/<default_branch> HEAD    # must exit 0
git push -u origin <branch>
git rev-list --left-right --count <branch>...origin/<branch> # 0 0 = landed
```

then `pr.create` against the default branch.

If `origin/<default_branch>` is not an ancestor of HEAD, a parallel session
pushed while you worked: rebase, never force-push.

Confirm the push by comparing refs, never by reading its output — `Everything
up-to-date` and exit 0 is also what a push that delivered nothing prints.

Open the body with the forge's closing keyword and the issue number so the issue
closes on merge; write the body to a file rather than passing it inline. Write it
for a reviewer who has read the issue and not your diff: lead with what the issue
got wrong or missed, then what's here, the evidence, what you verified and how,
what you could **not** verify and why, test results, and docs.

The linked pull request is now the claim, so `issue.assignee-remove` the
logged-in user and `issue.label-remove` the claim label.

If the project's conventions require an agent signature, post `developed-issue`
on the issue and `opened-pr` on the pull request
(`references/agent-signature.md`). This workflow is `work-issue`.

**Do not close the issue by hand, bump a version, tag, or deploy.** Opening a
pull request is not shipping, and this workflow does not ship even where the
project allows it.

Then remove the worktree and undo its provisioning, unless you are about to act
on review feedback.

## 9. Report back

The **pull request description** is for a reviewer who will read the diff. This
**report** is for the person who asked. Both obey `references/recap.md` — read it
for who the reader is, the readability contract, and the one hard rule. What
follows is only this workflow's required shape.

**Header — three lines, no heading.** The pull request link, the branch name, the
issue link.

**1. What we asked for.** The issue's ask in the requester's terms, plus its
acceptance criteria verbatim if it stated any. This is the yardstick.

**2. What was actually wrong.** The real mechanism in plain language: what
triggered it, what the visible consequence was, and how you confirmed it rather
than assumed it. State plainly where the issue's own diagnosis was incomplete.

**3. Decisions I took.** The forks you actually hit — the decision, the
alternative, why, and what it costs us later. Only real forks; mark any the
reader might reasonably overrule.

**4. What's now different.** Before → after on surfaces the reader knows,
including the parts the issue did not ask for but the fix required, and anything
you deleted.

**5. Evidence.** A table mapping each acceptance criterion to what satisfies it
and how you checked it:

| Asked for | Satisfied by | Verified how |
|---|---|---|

Then two lines: the gate result including any pre-existing failures and whether
they are yours, and the explicit docs outcome.

**6. Open, and what I did not do.** Assumptions the reader should confirm;
anything you could not verify and why; problems found outside scope; anything you
scoped down.
