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
| `issue.view` | `gh issue view <N>` |
| `issue.view-comments` | `gh issue view <N> --comments` |
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
| `pr.view` | `gh pr view <N>` |
| `pr.diff-names` | `gh pr diff <N> --name-only` |
| `pr.for-current-branch` | `gh pr view` (no argument) |
| `pr.fetch-head` | `git fetch origin pull/<N>/head` |

## What to know

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
