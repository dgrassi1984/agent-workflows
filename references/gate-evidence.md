# Reusing gate evidence

This contract applies only when the overlay explicitly defines `gate_evidence`.
Otherwise keep each workflow's existing gate requirements.

1. Read the bound documentation. Fetch the current target and identify the exact
   candidate, including staged, unstaged, untracked and submodule inputs.
2. Run the bound `verify` command. A missing record, missing artifact, nonzero
   exit, incompatible environment or uncovered required stage means run the
   missing coverage required by `validation-policy.md` (the legacy `gate` when
   no cadence policy is configured).
   Do not translate a partially passing record into a candidate-wide pass.
3. Reuse only locally trusted or authenticated CI evidence. The verifier must
   match relevant source content, gate definitions, commands, toolchain and test
   configuration, and verify completion and retained artifact integrity.
   Matching a commit title, a PR comment, or a JSON file supplied by the author
   is insufficient. Evidence is validation, not a substitute for code review.
4. Reviewers independently assess behavior and test sufficiency. Run additional
   focused checks when a claim or failure class is not covered by the evidence.
5. Repairs, rebases and a moving target require a fresh selection and evidence
   verification. Rerun invalidated stages. An unchanged relevant content tree
   does not need a new run merely because its commit SHA changed on merge.
6. Before release, use the bound `release` command after version/changelog edits
   and before tagging or pushing. It must validate the final artifact and all
   required coverage. Reuse gameplay evidence only where those edits did not
   invalidate its inputs. Revalidate after any subsequent rebase or edit.

Retain the tested content identity, commands, environment, results, durations
and artifact locations in the handoff. A failed or interrupted run never counts
as a pass; a retry must be reported alongside the original failure.
