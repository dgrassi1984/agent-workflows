# A procedure that has quietly re-bound itself to one project

This file exists to prove `check_unbound.py` can fail, and to prove it can still
fail **for every rule**. Each line below trips exactly one category. If
`make guard-test` ever passes, the guard is broken and every other green run
means nothing.

Run the gate with `uv run pytest` before pushing.
Claim the issue with `gh issue edit <N> --add-label X`.
Only take issues labelled human-approved, and skip design-needed.
Rebuild the Tailwind bundle first.
Read docs/CODEMAP.md and AGENTS.md for the conventions.
Deploy the acme image to the box.
