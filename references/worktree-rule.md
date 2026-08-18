# Every workflow that writes code works in its own worktree

This is the canonical copy of the rule. The workflows point here rather than
repeating it.

Applies whenever the overlay says `project.primary_checkout: read-only`, which is
also the default when a project has no overlay at all.

## The rule

**The primary checkout is read-only for a workflow.** You may read history there
(`git log`, `git show`, `git diff`, `git fetch`) and run the forge CLI there. You
may **not** run anything that moves its `HEAD`, its index or its files: no
`git checkout` / `switch` / `checkout -B`, no `git stash`, no
`git checkout <ref> -- .`, no `git reset`, no commit, no edit.

Everything else — the branch, the edits, the tests, the app you drive, the
commit, the push — happens in a worktree created for that one piece of work.

## Why, specifically

Several sessions share the primary checkout and move it under each other.

- **The branch moves between two of your commands.** So a commit lands on
  another session's branch, and `git push origin <default>` then reports
  `Everything up-to-date` and exits 0 — success output, nothing delivered.
- **The index is shared.** So `git add -A` sweeps in another session's staged
  work.
- **The files move.** So a session reading a file mid-way gets the other
  branch's version.

A worktree fixes the first one *structurally* rather than by convention: **git
refuses to check a branch out in two worktrees at once**, so once your branch is
yours it cannot be taken. The other two stop being possible because you are not
touching the shared tree at all.

This is not a hypothetical. It is the failure that reports success.

## Create it

Worktrees are **siblings of the repo** — `worktree.root` in the overlay, and
`../<repo>-<slug>` when it says nothing.

```bash
cd <primary checkout>
git fetch -q origin
git worktree add -b <type>/<slug>-<N> ../<repo>-<slug> origin/<default_branch>
cd ../<repo>-<slug>
```

`<type>` comes from `forge.branch_prefixes`; the issue number on the end makes the
branch self-describing and makes a stray claim findable by
`git ls-remote --heads origin`.

Branch from `origin/<default_branch>`, never from the primary checkout's `HEAD` —
you now know what that can be.

`git worktree` works from **any** worktree of the repo, and it resolves a
relative path against your current directory. Do not reach for
`git -C ../<repo> worktree add ../<dir>`: `-C` moves the directory the path is
resolved against, so that command creates the new tree *inside* the repo. Just
`cd` to where you want the sibling to appear and add it from there.

**Reviewing rather than building?** You want no branch of your own — detach at
the head under review instead:

```bash
git worktree add --detach ../<repo>-review<N> <SHA>
```

## Provision it

A fresh worktree has the code and nothing else. Whatever else it needs —
secrets, a private database, a free port, a compiled asset — is a project fact,
and the overlay's `worktree.provision` points at the document that lists it.
**Read that document before running anything from the new tree**; every item on
such a list is there because skipping it fails quietly rather than loudly.

If the overlay names no `provision` doc, a fresh worktree is assumed to run
as-is. Say so if something then fails for want of setup, rather than improvising
a fix that leaves the next session with the same surprise.

Two things are true in every project:

- **Never share the primary's development database.** Two servers writing one
  database is how a session verifies against another branch's data and believes
  it. If the project has one, the provisioning doc says how to clone it.
- **Never point a development server at the test database.** Test runners
  create, truncate and drop; a suite run has already destroyed development data
  somewhere by exactly this route.

## Run the app from it

Serve **from your worktree, on its own port, against its own data**. A page
fetched from another session's server shows their branch while looking exactly
like proof of yours.

Whatever you drive, **check the port belongs to the tree you think it does**
before reading anything off the page. The version in the footer and the data on
the screen both look equally convincing from someone else's server.

## Commit, push, and confirm from it

The commit rules do not change: never `git add -A`, always explicit pathspecs,
options before the `--`, look at `git diff --cached` before committing. What the
worktree adds is that the branch under you is yours and cannot be swapped — so a
mistaken commit is your own mistake, not a race.

```bash
git rev-parse --abbrev-ref HEAD                              # yours, always
git fetch -q origin
git merge-base --is-ancestor origin/<default_branch> HEAD     # must exit 0
git push -u origin <branch>
git rev-list --left-right --count <branch>...origin/<branch>  # 0 0 = landed
```

**Never confirm a push by reading its output. Compare the refs.** If
`origin/<default_branch>` is not an ancestor of `HEAD`, a parallel session pushed
while you worked: rebase, never force-push. Rewriting a pull request's source
branch is a different job and lives in `land-prs.md`: exact
`--force-with-lease` bound to the reviewed remote SHA, never `--force`.

## Remove it when the work is done

Once the pull request is open and the push is confirmed, the branch lives on the
remote and the worktree holds nothing you would miss.

```bash
cd <primary checkout>
git worktree remove ../<repo>-<slug>     # refuses if dirty; look before --force
git worktree prune                       # picks up directories deleted by hand
```

Take anything the provisioning step created with it — a per-worktree database, a
container, a reserved port. A stale one is a trap for the next session, and each
worktree left behind keeps its branch checked out, which blocks that branch
everywhere else.

Keep the tree only if you are about to act on review feedback.
