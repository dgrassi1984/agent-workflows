---
name: create-issue
description: >-
  File a tracked issue — check it is not already filed, measure the claim through
  the production entry point rather than a proxy, label it, and write it so a
  human can act on it months later without the conversation that produced it. Use
  whenever the user wants something recorded rather than fixed now — "file an
  issue for this", "add that to the backlog", "record it for later", "turn these
  findings into issues" — and when a session turns up a defect or a gap that is
  out of scope to fix here. Covers features and improvements as much as defects.
  Do not use it to implement an issue, to review a pull request, or to fix
  something small enough that filing it costs more than fixing it.
argument-hint: "[the feature request or the finding, in your own words]"
display_name: "File an Issue"
short_description: "File a measured, properly labelled issue"
wrapper_note: |-
  **Start** in the project's primary checkout — the forge CLI derives the
  repository from the current directory's git remote — and filing an issue never
  changes that checkout. If attributing a regression needs a second tree, use a
  throwaway worktree, never a `checkout` or a `stash` there.

  Filing is outward-facing: take one explicit go-ahead on the title, labels and
  summary before creating.
---

# File a tracked issue

One finding or one request in, one issue out that somebody can act on months
later without the conversation that produced it.

It covers **features and improvements as much as defects**. The skeleton below
carries both: a feature says what we want, a defect says what should be true and
is not. The evidence, the acceptance criteria and the labels work the same way.

## Before anything: read the bindings

`references/project-overlay.md`, then this project's overlay — it names the
forge, the label scheme, and what an agent may never set. Then
`references/forge-<kind>.md` for the command behind each `operation` named below.

With no overlay: file the issue with no labels rather than inventing a scheme,
and say that you did.

## Input

The ask, as the argument: a feature request in the user's words, a defect you
found, or "the findings from this session". If several distinct things arrived at
once, see *One issue per decision* — resist filing one big issue.

## 1. Is it already filed?

Three searches, not one. Issues, pull requests and branches each hide duplicates
the others do not: `issue.search`, `issue.search-closed`, `pr.open-list`, and

```bash
git ls-remote --heads origin | grep -i "<keyword>"
```

Two open issues can also describe the same thing from opposite ends and
contradict each other. If you find that, say so in the new issue and link both
rather than filing a third opinion.

## 2. Measure it before you write it

**This is the step that makes an issue worth having.** A number in an issue
outlives the session that produced it and becomes somebody's acceptance criteria.
Get it wrong and the fix is wrong.

- Reproduce the number **through the production entry point** — the function the
  route calls, the page as it renders. A `COUNT(*)` on a table, a command-line
  verb, or a lower-level helper measures something adjacent to the claim. A
  careful, honest measurement taken through a proxy is still a wrong number, and
  it will be repeated downstream by people who have no reason to doubt it.
- If the claim is user-visible, **drive the system and read what it actually
  produced**. Do it from a worktree on its own port and its own data
  (`references/worktree-rule.md`) so you are not measuring another session's
  branch.
- If the claim is about a rendered surface, rebuild whatever the project
  generates at package time first. A rule that was never compiled does nothing,
  silently, and you will file a bug that does not exist.
- Record the exact command in the issue so the next person can re-run it.
- For a feature, measure the *size of the gap* it closes. "Nearly half" is an
  argument; "1,093 of 2,284" is a decision.

Never write a number you did not run. If you cannot measure something the issue
depends on, put it under *Open questions* as a thing to measure, and say so.

## 3. If it is a regression, attribute it

Before filing "X is broken", establish whose it is — otherwise the issue blames
the wrong change and gets closed as unreproducible. Use detached worktrees, never
a `checkout` or a `stash` over the shared tree:

```bash
git worktree add --detach ../<repo>-attr-branch <suspect-sha>
git worktree add --detach ../<repo>-attr-main origin/<default_branch>
```

Provision both the same way and run the same test in each. Report the result as a
table of trees in the issue, then remove both trees and undo their provisioning.

## 4. One issue per decision

If the finding contains a genuine either/or, that is a decision, and it gets
stated as one — with a blocking label if the project has one and the shape is a
product question. Do not smuggle it into acceptance criteria; whoever implements
it will pick one silently and you will find out at review.

If the ask bundles several independent changes, split it. A bundle that mixes a
schema change, a logic simplification and an interface change cannot be finished
or reviewed as one thing, even when each part is fine.

## 5. Write the body

Write it to a file first — an inline body mangles backticks, `$` and newlines,
whatever the forge.

**The first half of the issue is for someone deciding whether to schedule it,
not for the implementer.** Plain language, name the surface not the module, give
the size of the thing in numbers anyone can read. Everything needing repo
knowledge goes below the marked boundary.

Drop any section with nothing genuine in it — an empty *Non-goals* is better
deleted than padded.

```markdown
## Summary
What somebody cannot do today, in plain language. Name the surface. No table
names, no function names. Three to five sentences.

**In one line:** the ask, as a single sentence.

## Why it matters
Who is blocked and what it costs them. If the system already solves the same
problem somewhere else, say where — an in-product precedent is the strongest
argument there is, and it tells the implementer what to copy.

## What we know today
The measured facts, as a small table, with the date. Then one short paragraph:
how this was checked, and through which entry point.

## What it should do
Acceptance criteria, each observable by a person using the system. Include the
standing rules that apply — a bookmarkable URL, surviving a browser Back, an
empty result saying so plainly rather than rendering blank.

## Non-goals
What this deliberately does not cover, so scope cannot drift into it.

## How we'll know it works
What to exercise, what to cross-check, what regression test pins it.

## Technical notes
*From here down assumes familiarity with the code.*

Modules, symbols, the read path, the trap the implementer will hit. Cite stable
symbols, not line numbers — line references are only for files with no symbol to
name.

## Open questions
Genuine unknowns and decisions the owner holds. Delete the section if there are
none; do not use it to hedge.
```

Titles state the thing in business terms, specific enough to find in a list:
`Movements: let me find the 1,093 movements with no category` beats
`Add category filter`.

## 6. Labels and milestone

**Labels are how a backlog is filtered; an unlabelled issue is invisible.** List
them live with `label.list` rather than trusting any document — they drift.

The rules, in terms of the overlay:

| | |
|---|---|
| `issues.severity_labels` | **exactly one, always**, if the project defines a scheme. Highest = data loss, security, or a crash affecting everything. Then: incorrect data or a crash on a common path. Then: misleading behaviour on an edge path, or friction. Lowest: polish, minor inconsistency, defense-in-depth. |
| type | the project's "broken" label only for something broken. A feature or improvement gets the enhancement label and **no** bug label — this is the most common mislabelling. |
| `issues.block_labels` | the shape is open and must not be invented by an agent. |
| `issues.approved_label` | **never set this yourself.** It means a human reviewed the issue and cleared it to build, and it is what a batch workflow's queue reads. Setting it at creation forges that approval. |
| `issues.claim_label` | **never set this at filing.** It is the claim that a session is already working the issue. |
| everything in `issues.never_set` | exactly what it says, including the assignee. Who does the work is the owner's call, and an auto-assigned issue reads as claimed when it is not. |

**Milestone is a scheduling decision, not yours.** Propose one only if the issue
plainly belongs to an open milestone, and let the human say yes.

## 7. Confirm, then create

Filing an issue is outward-facing and other people will read it. Show the
**title, labels, proposed milestone and the Summary section**, and take one
explicit go-ahead for the whole thing — do not walk through it field by field.

Then `issue.create`.

## 8. Verify, then report

Creation can succeed with a label silently dropped. Read it back with
`issue.view`: title, labels, milestone, no assignee.

Link what it came out of — an issue that came from reviewing a pull request, or
that supersedes another, is far more useful linked than described. This is the
step most often forgotten.

If the project's conventions require an agent signature, post one now
(`issue.comment`) using `references/agent-signature.md`. This workflow is
`create-issue`; the action is `filed-issue`. Do not invent a different pair.

Report the issue number and URL to the user, with the labels you set.

## What not to file

- Anything the code, a generated map or the history already records.
- Anything you could fix in less time than the write-up takes — fix it and say so.
- A vague code smell, or a hunch you have not measured. Measure it or drop it.
- A restatement of an open issue. Comment on that one instead.

A backlog is only useful if every item in it is worth reading. One well-measured
issue is worth ten plausible ones.
