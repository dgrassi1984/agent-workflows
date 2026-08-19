<!-- unbound-check: exempt — this file IS the GitHub dialect -->

# Forge dialect — GitHub (`gh`)

Used when the overlay says `forge.kind: github`. The workflows name an
**operation**; this file is the only place that knows the command.

`gh` derives the repository from the current directory's git remote, so run it
from a checkout of the project. `-R <owner>/<repo>` overrides that when you are
somewhere else.

Verified against `gh` 2.64.

| Operation | Command |
|---|---|
| `issue.view` | `gh issue view <N> --json number,title,body,author,state,labels,milestone,assignees,url` |
| `issue.view-comments` | `gh issue view <N> --json comments` |
| `issue.queue` | `gh issue list --state open --label <approved_label>` |
| `issue.search` | `gh issue list --search "<terms>"` |
| `issue.search-closed` | `gh issue list --state closed --search "<terms>"` |
| `issue.labels-of` | `gh issue view <N> --json labels --jq '.labels[].name'` |
| `issue.label-add` | `gh issue edit <N> --add-label <label>` |
| `issue.label-remove` | `gh issue edit <N> --remove-label <label>` |
| `issue.create` | `gh issue create --title "<t>" --label "<a,b>" --body-file <path>` |
| `issue.comment` | `gh issue comment <N> --body-file <path>` |
| `issue.close` | `gh issue close <N> --comment "<why>"` |
| `label.list` | `gh label list` |
| `pr.open-list` | `gh pr list --state open` |
| `pr.search` | `gh pr list --state open --search "<terms>"` |
| `pr.create` | `gh pr create --base <default_branch> --head <branch> --title "<t>" --body-file <path>` |
| `pr.comment` | `gh pr comment <N> --body-file <path>` |
| `pr.view` | `gh pr view <N> --json number,title,body,author,state,labels,url,headRefName,baseRefName,isDraft` |
| `pr.diff-names` | `gh pr diff <N> --name-only` |
| `pr.for-current-branch` | `gh pr view --json number,title,body,author,state,labels,url,headRefName,baseRefName,isDraft` |
| `pr.fetch-head` | `git fetch origin pull/<N>/head` |
| `pr.update-body` | `gh pr edit <N> --body-file <path>` |
| `pr.checks` | `gh pr checks <N> --required` |
| `pr.merge` | `gh pr merge <N> --match-head-commit <SHA>` plus the repository's customary `--merge` / `--squash` / `--rebase`, and `-d` only if this repo deletes source branches |

## What to know

- **Default `gh issue view` / `gh pr view` (no `--json`) query Projects (classic).**
  On the verified `gh` 2.64, GitHub answers that field with
  `GraphQL: Projects (classic) is being deprecated... (repository.issue.projectCards)`
  and **nothing else** — exit 0, no title, no body. Retrying the same command
  produces the same line. Always pass `--json` with explicit fields, and never
  ask for `projectCards`.
- **The closing keyword is `Closes #<N>`**, in the pull request body. One line per
  issue. Merging the PR closes them.
- **`--body-file` exists everywhere it matters.** Write the body to a file rather
  than passing `-b "..."` — inline bodies mangle backticks, `$` and newlines.
- **`FETCH_HEAD` is a single shared ref.** After `pr.fetch-head`, resolve it once
  (`git rev-parse FETCH_HEAD`) and use the SHA from then on. The next session to
  fetch in the same checkout overwrites it, and your later commands then
  silently describe their branch.
- **Creation can succeed with a label silently dropped.** Read it back with
  `issue.view` before reporting the issue as filed.
- **`--match-head-commit` is the source-SHA guard.** Never omit it. Never pass
  `--admin` to skip required checks. Confirm the merge by fetching the target
  and comparing trees, not by the command's success message.
- **`gh pr checks --required` is scoped to the pull request.** Pending required
  checks exit 8; that is not a pass. Confirm the check run is on the SHA you
  are about to merge.
