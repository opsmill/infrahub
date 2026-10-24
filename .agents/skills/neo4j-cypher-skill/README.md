# neo4j-cypher-skill

Generates, optimizes, and validates Cypher 25 queries for Neo4j 2025.x and 2026.x.

## Topics covered

**Query writing** — reads, writes, subqueries, batch operations, LOAD CSV, schema inspection, EXPLAIN/PROFILE validation

**Patterns** — MATCH, OPTIONAL MATCH, WITH, UNION, MERGE (constrained-key rules), FOREACH, UNWIND, CALL IN TRANSACTIONS

**Subqueries** — `EXISTS {}`, `COUNT {}`, `COLLECT {}`, `CALL (x) { }`, `OPTIONAL CALL`

**Path expressions** — Quantified Path Expressions (QPEs), match modes (`DIFFERENT RELATIONSHIPS`, `REPEATABLE ELEMENTS`), path selectors (`SHORTEST 1`, `ALL SHORTEST`)

**Search** — vector search (`SEARCH` clause 2026.01+, procedure fallback for 2025.x), fulltext (`db.index.fulltext`)

**Schema** — `db.schema.visualization`, `SHOW INDEXES/CONSTRAINTS/PROCEDURES`, `apoc.meta.schema()` (preferred when APOC available)

**Performance** — Eager operator detection and fixes, parallel runtime, index hints, anti-patterns by severity

**Language features** — dynamic labels/properties (2025.01), type predicates (`IS :: INTEGER NOT NULL`), `OrNull` casting, `coll.sort()`, `btrim()`, date/time arithmetic, null handling, 40+ syntax traps

## Version coverage

Defaults to 2025.01-safe features. Items new in 2025.x are annotated `[2025.01]` in the reference files; 2026.x items `[2026.01]`.

## Not covered

- Driver migration → `neo4j-migration-skill`
- DB administration → `neo4j-cli-tools-skill`

## Reference files

Loaded on demand — not bundled into the main skill context:

| File | Contents |
|---|---|
| [`references/cypher-syntax.md`](references/cypher-syntax.md) | Full syntax reference: clauses, patterns, functions. Items introduced in 2025.x annotated `[2025.01]`; 2026.x items `[2026.01]`; older deprecated forms annotated `[replaces X]` |
| [`references/syntax-traps.md`](references/syntax-traps.md) | 40+ table of invalid → correct Cypher — SQL habits and pre-2025 syntax |
| [`references/performance.md`](references/performance.md) | Anti-patterns with severity levels, text vs fulltext index comparison, Eager operator triggers and fixes |

## Not covered

- Driver migration or version upgrade → `neo4j-migration-skill`
- Database administration (users, config, backups) → `neo4j-cli-tools-skill`
- GQL clauses: `LET`, `FINISH`, `FILTER`, and `INSERT` are valid in Cypher 25 (introduced via GQL conformance, mostly in Neo4j 2025.06); not available on older versions

## Related skills

| Skill | Purpose |
|---|---|
| `neo4j-getting-started-skill` | Zero-to-app: provision, model, load, explore, build |
| `neo4j-migration-skill` | Upgrade Cypher syntax and drivers across major versions |
| `neo4j-cli-tools-skill` | DB administration via `neo4j-admin`, `cypher-shell`, Aura CLI |

## Install

```bash
npx skills add https://github.com/neo4j-contrib/neo4j-skills --skill neo4j-cypher-skill
```
