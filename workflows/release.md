---
name: release
description: >-
  Cut a version from the default branch: decide the bump, update the version
  files and changelog, commit, tag, push, then (only where the overlay names a
  deploy procedure) follow that procedure and verify. Use when asked to cut a
  release, bump and tag, ship a version, or release what just landed. Also the
  workflow land-prs hands off to when ship.after_merge is true, and the
  workflow work-issue-batch follows after it merges a batch. Do not use it to
  implement an issue, to review or merge someone else's pull request, or to
  deploy without cutting a version.
argument-hint: "[optional: patch|minor|major, a version, or the merges that just landed]"
display_name: "Cut a release"
short_description: "Bump, tag, and optionally deploy from the default branch"
wrapper_note: |-
  **Start** in the project's primary checkout — the forge CLI derives the
  repository from the current directory's git remote — and treat that checkout
  as read-only. The bump, the tag and any deploy happen in a worktree of the
  default branch.

  This workflow does **not** merge pull requests. Merging is land-prs (or the
  shipping half of work-issue-batch). If nothing is on the default branch to
  release, say so and stop.
---

# Cut a version, then optionally deploy

One tree on the default branch in, one tagged version out — and where the
project names a deploy procedure, one deployed release whose running version
you actually read.

**This document owns the bump, the changelog, the tag, and the push.** How a
particular host is cut over, what pins the running image, whether migrations
run themselves: that is `ship.procedure`, and it is followed only after the
tag exists. Do not invent a deploy ritual, and do not put one in this file.

## Before anything: read the bindings

`references/project-overlay.md`, then this project's overlay. The keys that
carry this workflow are `ship.enabled`, `ship.authorization`,
`ship.versioning`, `ship.procedure`, `gate`, and `worktree.provision`. Then
`references/forge-<kind>.md` for any forge operation named below, and
`references/worktree-rule.md` before you create a tree.

**`ship.enabled` decides whether this workflow runs at all.** False, or
absent, or no overlay: stop. Do not bump, tag, or deploy. Say that shipping
is off.

`versioning.scheme: none` with no `ship.procedure`: stop and say so rather
than inventing a ritual. Scheme unset defaults to semver.

A `procedure` that still describes bumping, changelog, or tagging is
**behind this workflow**. Do those steps here, skip the repeated ones in the
procedure, follow only its deploy and verify parts, and say that it is
behind. Do not double-bump.

## Input

Any of:

- A bump level: `patch`, `minor`, or `major`.
- An explicit version.
- A handoff from `land-prs` or `work-issue-batch`: the default-branch SHA
  that now contains the work, and the pull-request / issue numbers.
- Nothing: release whatever is on the default branch since the last matching
  tag.

If the argument names a pull request that is not merged, stop. Merging is a
different workflow.

## Authorization

When `ship.authorization` is `pre-authorized`, run without asking per step.
When it is `ask` — or absent — take one explicit go-ahead before the first
thing that leaves the branch (the push of the version commit and tag).

A handoff does not change this. `after_merge` means "continue into this
workflow", not "skip authorization".

## 1. Worktree on the default branch

```bash
git fetch origin
git worktree add -b <type>/release-<version-or-slug> <worktree.root> origin/<default_branch>
```

Use a `chore` prefix if the overlay lists one, otherwise the first prefix it
lists. Provision per `worktree.provision`.

If this is a handoff, confirm `HEAD` is the SHA the caller named. If the
default branch has moved past it, inspect the extra commits before bundling
them into this release; do not silently include unrelated work, and do not
rewind the branch.

## 2. Is there anything to release?

Find the latest tag that matches `ship.versioning.tag` (default `v{version}`).

- If `HEAD` is already that tag, stop: there is nothing new.
- If there are no commits since that tag and this is not an explicit
  "tag the current tree anyway" request, stop.
- If there has never been a tag and no version file resolved either, ask
  rather than starting at `0.0.1` or `1.0.0` by guess.

## 3. Gate

Run every command in the overlay's `gate`, in order. **Never release on red
or error-skipped tests.** If the overlay names no gate, find the project's
own test command and confirm it with the user. Never report an ungated tree
as a release.

## 4. Decide the bump

An explicit version in the argument wins. An explicit `patch` / `minor` /
`major` wins next.

Otherwise `ship.versioning.bump` (default `infer`):

- **`patch`**: always patch.
- **`ask`**: always ask, with the inferred suggestion shown.
- **`infer`**: read the work being released — commits since the last matching
  tag, and the pull-request / issue titles a handoff named. A breaking
  change (deleted public surface, renamed env var, incompatible schema, a
  subject that says so) is **major**. A user-visible feature — a new
  capability, not a fix — is **minor**. Everything else is **patch**. Mixed
  work takes the highest. The overlay's `branch_prefixes` are a signal when
  a branch name is still in reach (`feat` vs `fix`), not a rule that beats
  the commit bodies.

  Ask only when the titles and bodies genuinely do not say. Do not ask
  whether a one-line bug fix is a patch.

Scheme `none`: skip this step and step 5–8 (no version files, no tag) and
continue at deploy if a procedure exists.

## 5. Resolve the current version

Read it from `ship.versioning.files`, in order. An empty list is auto-detect
per `references/project-overlay.md`. Every listed file that exists must
already agree; if they disagree, stop and say so.

If no file resolved, the numeric part of the latest matching tag is the
current version. If that also is missing, ask.

## 6. Write the next version

Bump under semver. Write that version into **every** file in the list,
including ones auto-detect found. Then `git status`: a tracked file that
rewrote itself because it embeds the version belongs in the same commit. Do
not `git add -A`. Do not edit unrelated files to "tidy up" a release.

## 7. Changelog

`ship.versioning.changelog`:

- `none`: skip.
- a path: that file, which must already exist — do not create one.
- unset: auto-detect per the overlay contract; if nothing is there, skip
  (do not invent a changelog).

If you are writing one: a new section at the top for this version and
today's date, in the style the file already uses. Lead with the user-visible
change and why it mattered, not a list of paths. The commit bodies and pull
request titles are the raw material. If the file keeps compare-link
footers, add this version's entry to match its neighbours.

**Do not invent a changelog format.** An empty or missing file means skip.

## 8. Commit, tag, push

```bash
git rev-parse --abbrev-ref HEAD
git add -- <the version files, the changelog if written, the rewritten lockfile if any>
git commit -F <message-file> -- <those paths>
git tag -a <tag> -m "<tag>"
git fetch origin
git merge-base --is-ancestor origin/<default_branch> HEAD    # must exit 0
git push origin HEAD:<default_branch> --follow-tags
```

- Subject: the version. Body: the bump reason (inferred from what, or
  asked), the files, the tag, and whether deploy will follow.
- Trailer: `Co-Authored-By: <assistant> <model> <noreply@…>`.
- Never `--force`. If `origin/<default_branch>` is not an ancestor, rebase
  the version commit onto it and redo the tag; do not force-push a release.
- Confirm the push by comparing refs, not by reading the command's output.
- Confirm the tag on the remote points at the version-commit SHA.

If the project's conventions require an agent signature and this release
has pull-request or issue numbers (a handoff), post `cut-release` on each
(`references/agent-signature.md`). This workflow is `release`. Standalone,
with no artefact, skip the signature rather than minting a place to put it.

## 9. Deploy and verify — only if `ship.procedure` names a document

Follow that document for **deploy and verify only**, and nothing else. It is
the project's because every remaining step is a project fact. Do not
improvise around a step that looks redundant; those documents are usually a
list of things that have each already cost something.

If there is no procedure, stop after the tag and say so: the version is
cut, nothing was deployed.

**Say exactly what you verified.** A clean health check plus a log tail is a
different claim from "verified in the interface", and both should be
reported as what they are. Where the deployed system is behind
authentication, an authenticated click-through is the operator's job — an
agent must never type a password into any field.

Verify the **running** version, not git, when the procedure has a place that
prints it. A tag that exists and a process that still serves the previous
version is a failed deploy, not a successful release.

## 10. Clean up

Remove only the worktree this release created, and undo its provisioning.
Do not close issues: merge closing-keywords already did, or the caller
(`work-issue-batch`) still will, with this version named.

## Completion report

`references/recap.md` carries who the reader is, the readability contract
and the one hard rule. Read it. What follows is only this workflow's
required shape.

Report:

- Previous version, new version, tag, version-commit SHA.
- Why that bump (inferred from what, asked, or explicit).
- Files written, changelog written or skipped and why.
- Gate result.
- Deploy: followed `ship.procedure`, skipped because there is none, or
  blocked — and exactly what you verified on the running system.
- Anything left on the default branch that was *not* included, and why.

Do not call it released until the tag is on the remote. Do not call it
deployed until you have read a running-version signal the procedure names,
or said that there was no deploy.
