<!-- unbound-check: exempt — this file IS the GitLab dialect -->

# Forge dialect — GitLab (`glab`)

Used when the overlay says `forge.kind: gitlab`. The workflows name an
**operation**; this file is the only place that knows the command.

Verified against `glab` 1.90 by reading each subcommand's `--help`. Where GitLab
has no equivalent, this file says so rather than offering a plausible flag.

**A pull request is a merge request here.** It is `mr`, not `pr`; it is written
`!123`, not `#123`; and "open" is `opened`. Everything a workflow says about a
"pull request" applies unchanged — only the noun and the command move.

| Operation | Command |
|---|---|
| `issue.view` | `glab issue view <N>` |
| `issue.view-comments` | `glab issue view <N> --comments` |
| `issue.queue` | `glab issue list --label <approved_label>` |
| `issue.search` | `glab issue list --search "<terms>"` |
| `issue.search-closed` | `glab issue list --closed --search "<terms>"` |
| `issue.labels-of` | `glab issue view <N> -F json` then read `.labels` |
| `issue.label-add` | `glab issue update <N> --label <label>` |
| `issue.label-remove` | `glab issue update <N> --unlabel <label>` |
| `issue.create` | `glab issue create -t "<t>" -l "<a,b>" -d "$(cat <path>)" -y` |
| `issue.comment` | `glab issue note <N> -m "$(cat <path>)"` |
| `issue.close` | `glab issue note <N> -m "<why>"` **then** `glab issue close <N>` |
| `label.list` | `glab label list` |
| `pr.open-list` | `glab mr list` |
| `pr.search` | `glab mr list --search "<terms>"` |
| `pr.create` | `glab mr create -b <default_branch> -s <branch> -t "<t>" -d "$(cat <path>)" -y` |
| `pr.view` | `glab mr view <N>` |
| `pr.diff-names` | `glab mr diff <N>` (no `--name-only`; use `git diff --name-only <base>...<sha>`) |
| `pr.for-current-branch` | `glab mr view` (no argument) |
| `pr.fetch-head` | `git fetch origin merge-requests/<N>/head` |

## Where it differs, and it matters

- **There is no `--body-file`, anywhere.** `glab issue create` and
  `glab mr create` take `-d/--description` as a *string*. Still write the body to
  a file, then pass `-d "$(cat <path>)"` — the reason for the file (backticks,
  `$`, newlines surviving your shell) is unchanged, and command substitution
  preserves them. `-d -` opens an editor, which is useless to an agent.
- **`glab issue close` has no `--comment`.** Closing with a real explanation is
  two commands: leave the note first, then close. Do not drop the explanation
  because the flag is missing — a bare close is the thing the workflows forbid.
- **Pass `-y`** to `issue create` / `mr create`, or the command waits on a
  confirmation prompt that no agent will answer.
- **The closing keyword is `Closes #<N>`** in the merge request description, same
  as GitHub, and it refers to an *issue* `#N` even though the MR itself is `!N`.
- **`glab mr diff` prints a diff, not names.** For a file list, resolve the head
  SHA and use `git diff --name-only <default_branch>...<sha>`.
- **JSON output is `-F json`** on `view`, `-O json` on `list`. They are not the
  same flag; check the subcommand rather than assuming.
