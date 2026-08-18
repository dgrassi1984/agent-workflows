# Extraction recipes and a worked generator

## What's worth extracting

Rank by *cost to discover on the fly*, not by how easy it is to dump. The best
map preloads what is expensive to find and omits what one command returns.

| Fact | Cost to discover live | Preload? |
|---|---|---|
| What is this module/table *for* | Impossible — nothing in the code says | **Yes** |
| Who writes it / who reads it | Several greps, often ambiguous | **Yes** |
| Entry points: routes, CLI verbs, jobs, events | Scattered across decorators | **Yes** |
| Dependency edges (FKs, imports) | Multiple greps | **Yes** |
| Full column/field lists | One command, instant, always right | **No** — detail file |
| Row counts, file sizes, timings | Cheap but volatile | **No** — gitignored file |

The trap is preloading field lists: they are the bulk of the bytes and the
cheapest thing to fetch on demand.

## Per-stack extraction

### Database schema

| Store | Objects + definitions | Columns | Foreign keys | Row counts (volatile) |
|---|---|---|---|---|
| SQLite | `SELECT name, type, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'` | `PRAGMA table_info(t)` | `PRAGMA foreign_key_list(t)` | `sqlite_stat1` after `ANALYZE` — no table scan |
| Postgres | `information_schema.tables`, `obj_description(oid)` for comments | `information_schema.columns` | `information_schema.table_constraints` | `pg_class.reltuples` (estimate) |
| MySQL | `information_schema.tables` (has a native `table_comment`) | `information_schema.columns` | `information_schema.key_column_usage` | `information_schema.tables.table_rows` |
| ORM-only | The migration/model files are the source of truth — parse those, not a live DB | | | |

**SQLite keeps your `CREATE TABLE` text verbatim**, comments included, in
`sqlite_master.sql`. That makes a trailing comment on the CREATE line a
drift-proof description. It cannot be retrofitted, though: altering an existing
table's DDL comment means rebuilding the table. Postgres has real
`COMMENT ON TABLE`, which *can* be set after the fact — prefer it there.

**SQLite row-count caveat:** `PRAGMA analysis_limit = N` with N > 0 caps recorded
values, so `sqlite_stat1` can be quietly wrong. Detect clustering at a round
bound+1 and label the counts approximate rather than presenting fiction.

### Entry points

| Stack | Pattern to match |
|---|---|
| FastAPI / Flask | `@app.<verb>("...")`, `@router.<verb>("...")` |
| Express / Koa | `app.<verb>('...')`, `router.<verb>('...')` |
| Rails | parse `config/routes.rb`, or `rails routes` |
| Django | `urlpatterns` in every `urls.py` |
| Spring | `@GetMapping` / `@PostMapping` / `@RequestMapping` |
| Go net/http, chi | `mux.Handle*`, `r.Get("...")` |
| CLI | the arg-parser's subcommand registrations, or the dispatch chain |
| Jobs | the scheduler registry / cron definitions / queue consumers |

**List duplicate paths rather than merging them.** Two handlers for one route is
exactly the thing a map should surface — it is a classic source of "I edited the
wrong function".

### Symbols per module

Use the language's own parser, never regex:

| Language | Tool |
|---|---|
| Python | stdlib `ast` — walk for `ClassDef` / `FunctionDef` at module level |
| JS/TS | `typescript` compiler API, or `tree-sitter` |
| Go | `go/ast`, or `go doc` |
| Rust | `syn`, or `cargo doc --output-format json` |
| Anything | `tree-sitter` (grammars for 100+ languages), or `ctags -x` |

## Attribution: the context-anchored match

The pattern that makes "written by / read by" trustworthy. One pass over all
files, two compiled regexes, identifiers folded to canonical case.

```python
WRITE_OPS = (r"INSERT\s+(?:OR\s+\w+\s+)?INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM|"
             r"CREATE\s+(?:TEMP\s+)?(?:TABLE|VIEW)(?:\s+IF\s+NOT\s+EXISTS)?|ALTER\s+TABLE")
READ_OPS  = r"FROM|JOIN"

alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
write_re = re.compile(rf'(?:{WRITE_OPS})\s+["\'`\[]?({alt})\b', re.I)
read_re  = re.compile(rf'(?:{READ_OPS})\s+["\'`\[]?({alt})\b', re.I)

# Case-insensitive matching returns the SOURCE's spelling, not the canonical
# one — fold it back or you get a KeyError on the first uppercase SQL string.
canonical = {n.lower(): n for n in names}
```

Sort the alternation **longest-first** so `core_orders` wins over `orders`.

Rank results: application code, then tests, then migrations. A migration writes
once at deploy time and would otherwise crowd out the module that owns the table
at runtime. Drop nothing — a table whose only writer is a migration is a static
lookup, and one whose only caller is a test is probably dead. Both are worth
seeing.

## Determinism checklist

The guard is only useful if identical inputs produce identical bytes.

- [ ] Every list sorted; no bare set iteration
- [ ] No timestamp, no wall-clock, no `git rev-parse` in the output
- [ ] Paths relative to repo root, POSIX separators
- [ ] Inputs enumerated by `git ls-files`, not a filesystem walk
- [ ] A test asserts `build() == build()`

For "is this current?", fingerprint the **inputs** (hash the concatenated sorted
definitions) rather than stamping the moment of generation. An input hash changes
exactly when something real changed; a timestamp changes always.

## Wiring the guard

Put it where the repo's gate already runs — a test file is usually the lowest
-friction home, and needs no new infrastructure.

```python
def test_committed_map_matches_the_code():
    files = build()                      # regenerate in memory
    drifted = [rel for rel, expected in sorted(files.items())
               if not (ROOT / rel).exists() or (ROOT / rel).read_text() != expected]
    if drifted:
        pytest.fail("the committed map no longer matches the code:\n  "
                    + "\n  ".join(drifted) + "\n\n" + diagnose())
```

`diagnose()` earns its place. At minimum distinguish:

- **the map is behind the code** → regenerate and commit
- **your database/environment is behind the code** → migrate first; regenerating
  here would commit a map of a *stale* schema

Compare migration **name sets**, never counts — counts disagree for innocent
reasons (a migration file deleted after being applied leaves more rows than
files) and would report a healthy environment as behind, which is the one thing
this diagnostic must never do.

## Seeding descriptions with an LLM

Only if the source has no native place for the text. Rules:

- **Incremental and idempotent** — process only entries missing *or* stale, so
  the first run covers everything and later runs cover the one thing you added.
- **Commit the output with a fingerprint** of what it describes.
- **Scale the token budget to the batch** and salvage complete entries from a
  truncated reply. A fixed ceiling loses the whole batch when a reasoning model's
  hidden tokens eat the allowance.
- **Checkpoint each batch to disk** so a crash keeps the work.
- Never call the model at read time. The map must be readable offline.

## Distribution

Everything is a file in the repo, so `git pull` is the install.

| File | Purpose |
|---|---|
| `AGENTS.md` | Codex and most other agents read this by convention |
| Claude instructions file | Auto-loaded by Claude Code |
| `README.md` | One line, so humans find it too |

Keep one source of truth: have `AGENTS.md` *point at* the detailed conventions
file rather than duplicating it. Two copies of a convention is how conventions
drift — the exact failure this skill exists to prevent.

**Do not commit a session-hook config.** It executes a command on every
teammate's machine as soon as they pull, and hook configs are commonly gitignored
as per-developer settings. Ship the hook as a documented opt-in snippet for their
personal settings file, and put the always-on pointer in the instructions file
that is already committed and already read.
