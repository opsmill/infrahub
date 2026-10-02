# neo4j-query-tuning-skill

Diagnoses and fixes slow Neo4j Cypher queries by interpreting execution plans, identifying bad operators, and prescribing targeted fixes.

## What it covers

- **EXPLAIN vs PROFILE** — when to use each; key metrics (dbHits, rows, estimatedRows, pageCacheHitRatio)
- **Execution plan operators** — complete reference table with good/bad signals and fix strategies
- **Cardinality estimation** — detecting stale stats, forcing replanning
- **Common plan problems** — missing indexes, CartesianProduct, Eager, over-traversal
- **Planner hints** — `USING INDEX`, `USING SCAN`, `USING JOIN ON`
- **Runtime selection** — slotted, pipelined, parallel; when each is appropriate
- **Query monitoring** — `SHOW QUERIES`, `SHOW TRANSACTIONS`, `TERMINATE TRANSACTION`, `db.stats.retrieve`

## Availability

Works with any Neo4j 2025.x / 2026.x instance (self-managed or Aura). Some features require Enterprise edition:
- `SHOW QUERIES` for other users' queries — Enterprise
- `runtime=parallel` — Enterprise or Aura Pro 2025+

## Install

```bash
# Using Claude Code (agentskills.io):
/skill install neo4j-query-tuning-skill
```

## Reference Files

- [`references/plan-operators.md`](references/plan-operators.md) — complete operator table with all variants
- [`references/stats-and-monitoring.md`](references/stats-and-monitoring.md) — SHOW QUERIES, SHOW TRANSACTIONS, db.stats.*, index health, page cache
