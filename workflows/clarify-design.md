---
name: clarify-design
description: >-
  Recap every open, approved issue that is still blocked on a product decision,
  in plain language a non-coder can act on; ask only the leftover decisions; then
  write the answers onto the issue and drop the blocking label so a later agent
  may build it. Use when asked to unblock the design queue, resolve blocked
  issues, or turn open interface questions into a buildable spec — "clarify the
  design issues", "ask me the leftover design questions", "unblock these once I
  decide". Do not use it to implement the issue, to file a new one, or to ship a
  batch.
argument-hint: "[optional: specific issue numbers]"
display_name: "Clarify Blocked Issues"
short_description: "Turn leftover design questions into a buildable spec"
wrapper_note: |-
  **Start** in the project's primary checkout — the forge CLI derives the
  repository from the current directory's git remote — and treat that checkout as
  read-only. Comments and labels go through the forge CLI; any edit to a document
  happens in a worktree.

  This workflow does not implement, release or deploy. It only asks, records the
  answer, and drops the blocking label.
---

# Turn leftover design questions into a buildable spec

One conversation in, a set of issues an agent may now build (or close) out. The
value is not the recap — it is that the recap plus the owner's answers live **on
the issue**, so the next session does not need this one.

## Before anything: read the bindings

`references/project-overlay.md`, then this project's overlay. The queue is
`issue.queue` filtered to those also carrying a label from
`issues.block_labels` — those are the two names this workflow turns on.

If the overlay names no block labels, this workflow has no queue. Say so, and ask
which issues the user means rather than inventing a filter.

## Input

Optionally the user names specific issue numbers. If so, take those instead of
the whole queue.

## Authorization

Ask, then write the answers onto the issues. Do not implement. Do not set the
approval label (it is already there). Do not invent a shape while waiting for an
answer.

## The loop

### 1. Read the whole issue, then the code

`issue.view` and `issue.view-comments`. A later comment often revises the body.

Then check what already shipped. An issue can have had a first slice merged and
been left open on purpose. Recap **what a user can already see** versus **what is
still open**. Do not ask a question the code has already answered.

### 2. Recap in the owner's language

No file paths, no accessibility role names, no function names in the recap. Name
the surface and the feeling: "on a phone that page still slides sideways"; "this
screen used to light up that one as well". Keep the implementer detail for the
comment you will write after they answer.

### 3. Ask only leftover decisions

One question per issue. Offer two or three concrete options, recommended first.
Multi-select only when the leftover calls are independent.

Do **not** ask:

- something the issue or a later comment already decided;
- an implementation choice the codebase already has a convention for;
- whether to add tests — that is not a product decision.

If the first slice is already the whole user-visible fix, one of the options must
be **close as done**.

### 4. Write the answer onto the issue

After they pick:

- `issue.comment` in two halves. First half: the recap and the decision, in the
  same plain language as the ask. Second half, below a `---` and a
  `For the implementer` heading: the acceptance that is now closed, what is out
  of scope, and any file pointers that were already in the issue.
- `issue.label-remove` the blocking label once the leftover shape is specified.
  The approval label stays. A later implementation workflow may take it.
- If they chose **close as done**, `issue.close` with that same comment and leave
  the blocking label off. Do not keep a finished issue open as a container for a
  follow-up you have not filed.

Do not rewrite history. The original body stays; the comment is the addendum.

### 5. Report what you did

For each issue: recap, decision, new state (blocking label dropped / closed).
Then stop. Implementation is a different command.

## When genuinely stuck

If they pick an option that still leaves a shape open ("design something nicer"),
keep the blocking label and say so. If two issues now contradict each other, say
so on both and do not drop the label on either until they pick a winner.
