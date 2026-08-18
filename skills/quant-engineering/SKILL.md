---
name: quant-engineering
description: Use when working on backtests, trading systems, market data pipelines, P&L or performance accounting, signal and factor construction, rankings and scoring, or any pandas/numpy numeric code. Covers the silent-failure classes that corrupt results without raising — timestamp resolution mismatches, NaN propagation, tie inflation, double counting — plus how to sanity-check a suspicious metric before writing a post-mortem.
---

# Quant engineering

The failures here are almost never crashes. They are silent wrong numbers that
pass every test and look plausible on screen. Assume any surprising result is
an instrument bug until a control proves otherwise.

## Before you post-mortem a strange metric, run a control

A flat, zero, extreme or too-good number is a measurement claim, and it needs
the same scrutiny as a trading claim.

- **Null-signal control** — a random or shuffled signal should come out at
  roughly zero after costs. If it doesn't, the harness is broken, not the alpha.
- **Cost sensitivity** — re-run at 3× and 5× costs. A result that barely moves
  is suspicious.
- **Span-matched baseline** — compare against the same period, not a
  conveniently different one.
- **Cross-check external numbers against an independent source.**

Don't write three post-mortems of a broken zero. If two or three analyses land
on the same conclusion and it's being pushed back on, re-examine the measuring
instrument before re-examining the strategy.

**Pin every aggregator metric against an external "this == that" anchor**, not
just internal consistency. Internal consistency is satisfied by a pipeline that
is uniformly wrong.

## pandas / numpy silent killers

- **`pd.Timestamp.value` always returns NANOSECONDS**, regardless of the source
  index's resolution.
- **`DatetimeIndex.values.astype("int64")` returns the index's NATIVE
  resolution** — `datetime64[us]` in pandas 2.x for parquet-loaded indices.
- Comparing those two as raw int64 is silently wrong: the ns integers are
  ~1000× the µs integers. Use `idx.as_unit("ns").asi8` to force ns before
  extracting int64. This class of bug once zeroed an entire backtest accounting
  layer without raising anything — **grep-audit any `ts.value` + index-int64
  pattern during review.**
- **`Series.get(a) or Series.get(b)` raises truth-ambiguous** — write a
  `_coalesce` helper instead.
- **`.xs(level=…)` drops the level**, so a later reindex comes back all-NaN and
  silently turns into zero decisions.
- **`reindex(method='ffill')` will not fill an existing NaN label** — ffill
  first, then reindex.
- **A single transient NaN in a global feature poisons the whole universe** with
  no warning.
- **`if x is None` misses `''`.** Empty string is not None.

## Ranking, aggregation and counting

- **Tie inflation:** dense-rank ties let more than k rows into a "top-k" — which
  is how a percentage over 100 appears. Truncate to exactly k.
- **Double counting from raw name aggregation:** variant spellings of the same
  entity aggregate separately and then both count. Add a non-destructive merge
  layer rather than editing the source names.
- **Never sum incompatible measures.** Premium and notional are different units;
  a buy leg and a sell leg of the same trade are not two trades. Label the
  measure explicitly wherever it's displayed.
- Check logical invariants: YTD ≥ any single month within it; netting reduces
  *net* exposure, not gross.

## Signals and scoring

- **A single-day or few-sample z-score is too fragile to weight into a
  ranking.** Gate the pillar until periods stack, score on a ratio rather than a
  level, and abstain when coverage is missing.
- **An unvalidated lead/lag signal must not influence rankings** until a real
  lead/lag backtest has measured the lead.
- Build any within-run z-score baseline at the **same unit as the scored
  quantity**, or it saturates.
- **Never select a parameter on the same data you evaluate on.** Prefer round,
  loose values over finely tuned ones.
- **Enrichment must run idempotently on every path**, not just inside one entry
  point — data created by another path (a bulk job, a seeding script) is
  otherwise silently un-enriched and mis-ranked. Apply score transforms to the
  full persisted set, not just the subset you kept.

## Data sourcing

- **Anchor enums and identifiers against real data.** Invented domain codes
  return empty; an identifier that resolves in one reference dataset may 404 in
  another, so check which source actually resolves before relying on it.
- **Caps, seeds and timid prompts silently starve coverage.** Diagnose gaps
  empirically — check where the missing names actually rank, confirm the real
  universe size, and verify a suspected cause's row impact before blaming it.
- **Cross-source gaps can be definitional**, not errors. Surface a delta with a
  footnote rather than forcing a reconciliation.
- Treat a stale snapshot as a labelling problem: a KPI computed off one can show
  a fraction of the actual figure, so state the caveat on screen.
