# neo4j-driver-python-skill

Skill for writing Python applications that connect to Neo4j using the official Neo4j Python Driver.

**Covers:**
- Installation and driver lifecycle (singleton pattern, `verify_connectivity`)
- URI schemes and auth options (Aura, bolt, bearer, Kerberos)
- `execute_query` — default API with `RoutingControl`, `result_transformer_`, trailing-underscore convention
- Managed transactions (`execute_read` / `execute_write`) — retry safety, result lifetime, `@unit_of_work`
- Implicit transactions (`session.run`) — `LOAD CSV`, `CALL {} IN TRANSACTIONS`
- Async driver (`AsyncGraphDatabase`) — FastAPI lifespan pattern, `asyncio.gather`
- Error handling — `ConstraintError`, `ServiceUnavailable`, `TransientError`, GQL status codes
- Result access — `Record`, `record.data()`, JSON serialization gotchas
- Data type mapping — Python ↔ Cypher, temporal types, graph objects (`Node`, `Relationship`)
- UNWIND batch writes (`list[dict]` only)
- Connection pool tuning and session exhaustion
- Causal consistency and bookmarks

**Version / compatibility:**
- Driver v6.x (Jan 2026+) — package name is `neo4j`, not `neo4j-driver`
- Python ≥ 3.10 required

**Not covered:**
- Cypher query authoring → use `neo4j-cypher-skill`
- Driver version upgrades / breaking changes → use `neo4j-migration-skill`
- GraphRAG pipelines (`neo4j-graphrag` package) → use `neo4j-graphrag-skill`

**Install:**
```bash
pip install neo4j
```
