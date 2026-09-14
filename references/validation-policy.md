<!-- unbound-check: exempt — names the shared helper runtime, not a project toolchain -->

# Validation, checkpoints and handoffs

Use this contract from implementation, review, landing and release. Read it
once per task; reuse it unless its source changes. Explicit user instructions
override defaults, including already-authorized waivers and merge permission.

## Select work once

Before implementing, identify one representative production journey that will
prove the requested behavior. Run it early to catch integration/setup mistakes,
then after the fix. Choose focused checks for the changed failure modes. A
later reviewer checks the evidence and remaining risks, not a duplicate checklist.

With no `gate_policy`, the existing overlay `gate` remains required. With a
policy, run focused checks per candidate and the scheduled aggregate checkpoint.
Full supersedes fast when both are due. Cadence never makes a focused failure
acceptable. A release, explicit user request, or new concrete risk may need
additional coverage; state that reason before expanding validation.

## Execute and retain the result

The shared helper is `~/Development/agent-workflows/scripts/workflow_run.py`.
Its inline dependency metadata provisions the overlay-validator dependencies. Run it from the
candidate's isolated worktree:

```text
uv run --quiet <helper> plan
uv run --quiet <helper> run --tier focused --command '<focused check>'
uv run --quiet <helper> run
```

The last command is only for an aggregate tier selected by `plan`; when the
plan says focused, the explicit focused run is sufficient. Each repeated
`--command` is executed in order, stopping on the first failure. Keep result paths. Before merging, commit the exact tested contents. Evidence
can survive that commit because the helper compares file contents, modes and
submodule commits rather than requiring the original commit hash. Any material
change still invalidates it. Raw output goes to the accompanying log, with
only stage changes and the final result returned to the model.

The helper locks heavy work across projects and bounds queue wait, provisioning,
commands and retries. Start it with the normal asynchronous shell tool; inspect
completion with **one** bounded tool wait, or `watch <result-path>` (at most 55s).
If that wait returns still running, do useful independent work or end the turn and
let the completion notice arrive — do not take a second synchronous wait on the
same job. One bounded wait is the rule; a second one is a defect that costs the
session its responsiveness while the job runs anyway. Avoid loops of
model-driven sleeps, unchanged log tails and repeated “still running” commentary.
Preserve required user updates; summarize the stage and what its result will resolve.

**A refusal is a decision, not a status.** When the helper rejects an attempt —
same candidate already attempted, budget exhausted, missing evidence, a tier with
no commands — it has already answered. Inspect the result or log it names and
choose the next legal step; never wait on a job whose outcome was decided at
launch, and never restate the same request under a new name. Read `plan` first so
the refusal does not have to be discovered.

**Infrastructure failure is not a code failure.** A message about billing,
spending limits, quota, a disabled runner, an expired token or a forge outage is
a project blocker: report it, name what it blocks, and stop. Do not spend the
session reading CI logs or retrying a runner that cannot start; local gate
evidence already in hand stands on its own.

A retry requires a concrete `--retry-reason`, such as a verified environmental
correction; the same source/tier/policy keeps its original deadline even when
commands change. There is no automatic whole-suite retry. An exhausted budget
is an outcome, not a reason to restart under another name. Fixing source inputs
creates a new candidate. Apply the same discipline when a legacy gate runs
without this helper.

## Evidence and failures

Prefer `gate_evidence.verify` when provided. Reuse requires matching relevant
source inputs, toolchain, command/configuration, generated assets, completed
verdict and artifacts. A passed summary in a PR description is insufficient.
If the project cannot verify evidence, rerun the necessary checks. A changed
target invalidates assumptions about the integration tree; inspect and rerun
affected coverage, not automatically every unrelated check.

Distinguish assertion failure, infrastructure failure, interruption, timeout,
and pass. `gate_policy.timeout: waive` records a timeout as waived, never passed.
Inspect the log for failures already reported before a timeout; such failures
remain blockers and require repair or a separate explicit user decision.
The helper stops on the first failed command but cannot infer assertion state
inside a project's opaque aggregate command. Queue timeout is not test evidence.
Recording a waived result therefore requires `record-merge --timeout-reviewed`
after the agent inspects its logs for unresolved failures; this is evidence
review, not another request for the user's already-given timeout authorization.
Existing user authorization persists; do not request it again to resolve a
conflict with an unconditional sentence in another workflow.

## Advance the shared counter

Run `plan` immediately before merge and use its `merged_count`. After the normal
exact-SHA merge and remote fetch/readback:

```text
uv run --quiet <helper> record-merge --sha <merge-sha> --expected-count <count> --result <focused-result> --result <checkpoint-result>
```

Omit the checkpoint result when none was due. State lives in the Git common
directory, shared by sibling worktrees; it starts at zero when this policy is
adopted, not once per task. Recording a SHA twice is idempotent. A moved counter
requires recomputing coverage; never reset it or omit a landed merge. Exact
tested-content/merged-tree agreement is checked. Do not treat a stale-policy or
different-tree result as reusable. Concurrent merge workflows should serialize
their short plan/merge/readback/record phase to prevent a missed checkpoint.

For projects without `gate_policy`, record the full result if using the helper
to track release cadence. This mechanism records evidence and counters; it does
not itself authorize or perform a merge, publish or deployment.

## Release and task boundaries

`ship.release_cadence` defaults to `per-batch`, preserving existing projects.
`checkpoint` releases after `ship.release_every` recorded merges; `manual`
releases only on explicit request. These settings do not enable shipping or
deployment. `land-prs` still requires `ship.after_merge` or user authorization
to initiate automatic releases. Explicit release requests override the cadence.

At a release checkpoint, include every unreleased merge in the release handoff,
validate the final tree with the configured full/release coverage, and reuse
verified matching evidence. After the tag is pushed and read back, run
`record-release --tag <tag>`. That verifies the remote tag before marking its
ancestor merges released. A deferred release is reported as deferred, never as
a version already shipped; issue closure can cite the merge SHA meanwhile.

After each coherent batch, save a brief `handoff --note '<remaining work,
evidence limitations, and session-specific authorization>'`. It records SHAs,
evidence paths, release backlog and the next checkpoint. Use it when continuing
in a new task; do not replay the whole project history. Continue an authorized
queue without asking at every boundary; create another task only if the user
requested one. On stopping with unreleased work, leave it in the handoff rather
than silently making a release or losing the backlog.

## Bound a pass, then hand off

A large item is delivered as successive bounded passes, never as one unbounded
one. Set the bound before starting — steps taken, wall-clock, or the point where
the handoff already carries enough for someone else to continue — and treat
reaching it as a normal outcome, not a failure. Then hand off: what is committed,
the evidence and its limits, and exactly what the next pass should do first.

The reason is context, not stamina. Everything a pass has read, run and printed
stays in front of it, so a pass that overshoots keeps paying for its whole history
on every step while its actual output per step shrinks. A fresh pass re-reads the
handoff and the plan, not the transcript. Within a pass, a file already read is
already known — edit against that read rather than reading it again, and send long
command output to its log and read the tail instead of the whole thing. Re-reading
and re-printing are the cheapest-looking ways to spend the most.
