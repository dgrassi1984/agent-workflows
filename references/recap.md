# Writing the report back

Every workflow here ends by telling a person what happened. The audience differs
— someone deciding whether to merge, someone deciding whether this is what they
asked for — but the contract is the same, so it is written once, here. Each
workflow says what its own report must *contain*; this file says what every
sentence in it must *be*.

## Who you are writing for

Someone who knows the product, the architecture and the requirements cold — and
who has never read a line of this codebase. They are answering one question, and
your report is what they trust **instead of** reading the code.

Write it self-contained. Not a paste of the pull request body: same facts,
different sentences. Write it in the language the user has been writing in.

## The readability contract

Every sentence must be true at the level of *behaviour* — what the system now
does, on surfaces the reader already knows: screens, routes, jobs, tables,
dashboards. File and function names appear only as a pointer in brackets *after*
a sentence that already stands without them.

| Instead of | Write |
|---|---|
| "Refactored `_pct()` to normalise at the boundary." | "A weight typed as 12.5 is now stored as 0.125 instead of 12.5, so the allocation chart adds up to 100% (`investments.py`)." |
| "Added a guard in the template." | "A category with no movements no longer renders a blank table — the page says so explicitly." |
| "Fixed the aggregation." | "Monthly totals were counting a transfer on both sides. They are now ~18% lower and tie out to the bank statement." |

**The test: delete every backticked name from a sentence. If it stops meaning
anything, rewrite it.**

Never write "this looks risky". Give the scenario and the consequence, or drop
the finding.

## The one hard rule

**Never write a claim you did not verify.**

- A screen you did not drive → say it is unverified.
- A number that is an estimate → label it as one.
- A step you planned but did not run → it does not appear as done.
- A check that was a health probe → say that, not "verified in the browser".

An overstated report is worse than a thin one, because it removes the reader's
ability to catch the gap. A block with nothing genuine in it gets one honest
line, never filler.

## What must always be visible

Whatever else a workflow's shape requires, these three are never omitted:

1. **What you could not verify, and why.** Not as an apology — as the boundary of
   what the report covers.
2. **What you scoped down or left out, and why.** Scaling the work down is the
   reader's call, so it has to be visible for them to make it.
3. **Assumptions the reader should confirm**, and any decision they might
   reasonably overrule.

Aim for about two minutes of reading.
