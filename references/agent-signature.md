# Agent signatures

Every workflow here that writes to an issue or a pull request ends by signing
that write, so a later reader of the forge thread can see which harness and
model did what, and when. The format is the same on every project; only the
command that posts it comes from `references/forge-<kind>.md`.

The **names** live here because they are the workflow names. A project document
that lists a different closed set is behind this file — say so, and use these
names. Do not invent a `workflow` or `action` value. If what you did has no row,
that is a bug in this file: say so, and skip the signature rather than minting
one.

## When to sign

Sign when the project's conventions require it — they usually say so, or they
point at a signature document of their own. If they do not, do not post one.

The format and the names are this file either way. A project document may
describe the same comment; it does not get to rename a workflow.

## The format

A single-line comment, starting with a fixed prefix, then space-separated
`key=value` fields:

```
[agent-signature] ts=<ISO-8601> harness=<harness> workflow=<workflow> action=<action> model=<model> artifact=<issue-or-pr>
```

Example:

```
[agent-signature] ts=2026-08-18T16:02Z harness=dsh workflow=clarify-design action=clarified-design model=grok-4.6 artifact=#412
```

Post it with `issue.comment` or `pr.comment` as its own comment, on the thing
it describes. Do not append it to the recap you just wrote.

## Fields

| key | value | guaranteed? |
|---|---|---|
| `ts` | UTC ISO-8601 of the comment, minute precision is enough | yes |
| `harness` | `claude`, `codex`, `opencode` or `dsh` | **yes — deterministic** |
| `workflow` | the workflow you are running, from the closed set below | yes |
| `action` | from the closed set below | yes |
| `artifact` | the identifier the forge uses for the thing you commented on | yes |
| `model` | the model that did the work | agent-claimed, not verifiable |

`harness` is which of the four this repo installs into you are running as. Write
`claude` for Claude Code, `dsh` for DeepSeek Harness. Do not write a marketing
name or a wrapper path.

`model` is whatever you are actually running as. State it honestly rather than
the configured default if they differ.

`artifact` is `#N` for an issue. For a pull request it is whatever the forge
writes — `#N` on one, `!N` on another. Copy the identifier, do not translate it.

## The workflow vocabulary

| workflow | the procedure |
|---|---|
| `create-issue` | `workflows/create-issue.md` |
| `work-issue` | `workflows/work-issue.md` |
| `work-issue-batch` | `workflows/work-issue-batch.md` |
| `review-pr` | `workflows/review-pr.md` |
| `clarify-design` | `workflows/clarify-design.md` |

These are the filenames. They change when a procedure is added or renamed.

## The action vocabulary

| action | meaning |
|---|---|
| `filed-issue` | created the issue |
| `started-work` | claimed the issue and began implementing |
| `developed-issue` | implementation is on a branch; state the evidence on the issue |
| `opened-pr` | opened the pull request |
| `review-started` | began reviewing the pull request |
| `reviewed-pr` | review concluded (and merged, if asked) |
| `clarified-design` | wrote the owner's decision onto the issue and dropped the blocking label, or closed the issue as already done |

`work-issue-batch` reuses the `work-issue` actions. The `workflow` field is what
distinguishes a batch from a single issue.

Do not sign a clarification you only asked and have not written back. Do not
sign a review you have not finished. Do not sign an issue you kept blocked.

## Where each signature is written

| stage | comment on | workflow | action |
|---|---|---|---|
| issue filed | the issue | `create-issue` | `filed-issue` |
| starting work | the issue | `work-issue` or `work-issue-batch` | `started-work` |
| pull request opened | the issue and the pull request | `work-issue` or `work-issue-batch` | `developed-issue` (issue), `opened-pr` (pull request) |
| starting review | the pull request | `review-pr` | `review-started` |
| review concluded | the pull request and the linked issue | `review-pr` | `reviewed-pr` |
| design unblocked (or closed as done) | the issue | `clarify-design` | `clarified-design` |

Each workflow names the moment. This table is the closed map those moments
use, not a second procedure.
