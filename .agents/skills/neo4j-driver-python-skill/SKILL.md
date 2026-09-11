---
name: neo4j-driver-python-skill
description: Neo4j Python Driver v6 — driver lifecycle, execute_query, managed and explicit
  transactions, async (AsyncGraphDatabase), result handling, data type mapping, error handling,
  UNWIND batching, connection pool tuning, and causal consistency. Use when writing Python
  code that connects to Neo4j via GraphDatabase.driver, execute_query, execute_read,
  execute_write, AsyncGraphDatabase, neo4j.Result, or RoutingControl. Package name is
  `neo4j` (not neo4j-driver) since v6. Python >=3.10 required.
  Does NOT handle Cypher query authoring — use neo4j-cypher-skill.
  Does NOT cover driver upgrades or breaking changes — use neo4j-migration-skill.
  Does NOT cover GraphRAG pipelines (neo4j-graphrag package) — use neo4j-graphrag-skill.
version: 1.0.1
allowed-tools: Bash WebFetch
---

## When to Use
- Writing Python code that connects to Neo4j
- Setting up driver, sessions, transactions, or async patterns
- Debugging result handling, serialization, or UNWIND batching
- Reviewing Neo4j driver usage in Python code

## When NOT to Use
- **Writing/optimizing Cypher** → `neo4j-cypher-skill`
- **Driver version upgrades** → `neo4j-migration-skill`
- **GraphRAG pipelines** (`neo4j-graphrag` package) → `neo4j-graphrag-skill`

---

## Installation

```bash
pip install neo4j                  # package name is `neo4j`, NOT `neo4j-driver` (deprecated since v6)
pip install neo4j-rust-ext         # optional: 3–10× faster serialization, same API
```

**Python >=3.10 required** for v6.x. Python 3.14 supported [6.1+]. Pandas 3 and PyArrow 23/24 supported [6.2+].

---

## Environment Variables

Load connection config from environment — never hardcode credentials.

```python
import os
from dotenv import load_dotenv   # pip install python-dotenv

load_dotenv(".env")   # reads NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE

URI      = os.getenv("NEO4J_URI",      "neo4j://localhost:7687")
USER     = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
```

`.env` file format:
```
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=secret
NEO4J_DATABASE=neo4j
```

Add `.env` to `.gitignore`. Without `python-dotenv`, use `export` in shell or `os.getenv` directly.

---

## Driver Lifecycle

Create **one Driver per application**. Thread-safe, expensive to create. Never create per-request.

```python
from neo4j import GraphDatabase

URI  = "neo4j+s://xxx.databases.neo4j.io"   # Aura
AUTH = ("neo4j", "password")

# Context manager — preferred for scripts
with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()
    # ... work ...

# Long-lived singleton (service / web app)
driver = GraphDatabase.driver(URI, auth=AUTH)
driver.verify_connectivity()
# on shutdown:
driver.close()
```

URI schemes:

| Scheme | Use |
|---|---|
| `neo4j+s://` | TLS + cluster routing — **Aura default** |
| `neo4j://` | Unencrypted + cluster routing |
| `bolt+s://` | TLS, single instance |
| `bolt://` | Unencrypted, single instance |

Auth options: `("user", "pass")` tuple, `basic_auth()`, `bearer_auth("jwt")`, `kerberos_auth("b64")`.

---

## Choosing the Right API

| API | Use when | Auto-retry | Streaming |
|---|---|---|---|
| `driver.execute_query()` | Most queries — simple, safe default | ✅ | ❌ eager |
| `session.execute_read/write()` | Large results / multiple queries in one tx | ✅ | ✅ |
| `session.run()` | `LOAD CSV`, `CALL {} IN TRANSACTIONS`, scripts | ⚠️ one-shot [6.2+] | ✅ |
| `AsyncGraphDatabase` | asyncio applications | ✅ | ✅ |

`session.run()` retry [6.2+]: single immediate retry on DBMS-marked idempotent errors only (currently admission control). Disable with `disable_auto_commit_retries=True` at driver or session level.

---

## `execute_query` — Default API

```python
from neo4j import GraphDatabase, RoutingControl

# Tuple unpacking — most common
records, summary, keys = driver.execute_query(
    "MATCH (p:Person {name: $name})-[:KNOWS]->(f) RETURN f.name AS name",
    name="Alice",
    routing_=RoutingControl.READ,   # route reads to replicas
    database_="neo4j",              # always specify — saves a round-trip
)
for record in records:
    print(record["name"])
print(summary.result_available_after, "ms")

# Write — check counters
summary = driver.execute_query(
    "CREATE (p:Person {name: $name, age: $age})",
    name="Bob", age=30,
    database_="neo4j",
).summary
print(summary.counters.nodes_created)
```

**Trailing-underscore convention** — config kwargs end with `_` (`database_`, `routing_`, `auth_`, `result_transformer_`, `bookmark_manager_`). No query parameter name may end with `_`; pass those via `parameters_={"key_": val}`.

**Never f-string or format Cypher.** Always `$param` — prevents injection and enables plan caching.

`result_transformer_` — reshape before return:
```python
import neo4j
df      = driver.execute_query("MATCH (p:Person) RETURN p.name, p.age", database_="neo4j",
                                result_transformer_=neo4j.Result.to_df)
record  = driver.execute_query("MATCH (p:Person {name:$n}) RETURN p", n="Alice", database_="neo4j",
                                result_transformer_=neo4j.Result.single)   # raises if 0 or 2+ results
```

`Result.single()` raises `ResultNotSingleError` on **zero** results (not just 2+). Use `single(strict=False)` for None-on-empty.

---

## Managed Transactions (`execute_read` / `execute_write`)

Use for large results or multiple queries in one transaction.

```python
with driver.session(database="neo4j") as session:

    def get_people(tx):
        result = tx.run("MATCH (p:Person) WHERE p.name STARTS WITH $pfx RETURN p.name AS name",
                        pfx="Al")
        return [r["name"] for r in result]   # consume INSIDE callback — Result invalid after tx closes

    names = session.execute_read(get_people)

    def create_person(tx):
        tx.run("CREATE (p:Person {name: $name})", name="Carol")

    session.execute_write(create_person)
```

**Result lifetime** — `Result` is a lazy cursor backed by the open transaction. Returning it unconsumed raises `ResultConsumedError`. Always collect to `list` inside the callback.

**Callback may retry** on transient failures — keep callbacks idempotent; move side effects (HTTP calls, emails) outside the callback.

Timeout/metadata via `@unit_of_work` (named functions only — cannot decorate lambdas):
```python
from neo4j import unit_of_work

@unit_of_work(timeout=5.0, metadata={"app": "svc", "user": user_id})
def get_people(tx):
    return [r["name"] for r in tx.run("MATCH (p:Person) RETURN p.name AS name")]

session.execute_read(get_people)
```

---

## Implicit Transactions (`session.run`)

Use only for `LOAD CSV`, `CALL {} IN TRANSACTIONS`, or quick scripts. `session.run()` does a single immediate retry on idempotent (DBMS-marked) errors only [6.2+]; other errors do not retry.

```python
with driver.session(database="neo4j") as session:
    result = session.run("CREATE (p:Person {name: $name})", name="Alice")
    summary = result.consume()   # call consume() to guarantee commit before proceeding
    print(summary.counters.nodes_created)

# Opt out of one-shot retry [6.2+] — driver- or session-level
driver = GraphDatabase.driver(URI, auth=AUTH, disable_auto_commit_retries=True)
with driver.session(database="neo4j", disable_auto_commit_retries=True) as session:
    session.run("...")
```

---

## Async API

Mirror of sync API — replace `GraphDatabase` with `AsyncGraphDatabase`, `await` every call.

```python
from neo4j import AsyncGraphDatabase
import asyncio

# Singleton — same rule as sync: never create per-request
driver = AsyncGraphDatabase.driver(URI, auth=AUTH)

async def main():
    records, _, _ = await driver.execute_query(
        "MATCH (p:Person) RETURN p.name AS name",
        database_="neo4j", routing_=RoutingControl.READ,
    )
    print([r["name"] for r in records])
    await driver.close()

asyncio.run(main())
```

FastAPI lifespan pattern:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

_driver = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _driver
    _driver = AsyncGraphDatabase.driver(URI, auth=AUTH)
    await _driver.verify_connectivity()
    yield
    await _driver.close()

app = FastAPI(lifespan=lifespan)
```

Parallel queries with `asyncio.gather`:
```python
results = await asyncio.gather(
    driver.execute_query("MATCH (a:Artist) RETURN a.name AS name", database_="neo4j"),
    driver.execute_query("MATCH (v:Venue)  RETURN v.name AS name",  database_="neo4j"),
)
```

**Never use sync `GraphDatabase` in asyncio** — blocks the event loop.

Full async patterns → [references/async.md](references/async.md)

---

## Error Handling

```python
from neo4j.exceptions import (
    Neo4jError, ServiceUnavailable, TransientError,
    AuthError, ConstraintError,
)

try:
    driver.execute_query("...", database_="neo4j")
except AuthError:
    ...  # bad credentials
except ServiceUnavailable:
    ...  # no servers reachable
except ConstraintError as e:
    # unique/existence constraint violation — catch BEFORE Neo4jError (it's a subclass)
    print(e.code, e.message)
except TransientError as e:
    # raised only after retries exhausted (execute_query retries automatically)
    print(e.code)
except Neo4jError as e:
    print(e.code, e.message, e.gql_status)
```

Catch `ConstraintError` before `Neo4jError` — it is a subclass and will be swallowed otherwise.

---

## Result Access & Null Safety

```python
record = records[0]
record["name"]               # by key — KeyError if absent
record[0]                    # by index
record.get("name")           # None for absent key OR graph null
record.get("name", "Unknown")
d = record.data()            # dict — values still driver objects for Node/Rel/temporal types
```

`record.data()` is **not JSON-safe** if result contains `Node`, `Relationship`, `Path`, or `neo4j.time.*` values. Project scalar fields in Cypher instead of returning whole nodes.

```python
# ❌ raises TypeError on json.dumps
records, _, _ = driver.execute_query("MATCH (p:Person) RETURN p", database_="neo4j")
json.dumps(records[0].data())

# ✅ project scalars
records, _, _ = driver.execute_query(
    "MATCH (p:Person) RETURN p.name AS name, p.age AS age", database_="neo4j")
json.dumps(records[0].data())   # safe
```

Node/Relationship/temporal access:
```python
node = record["p"]           # neo4j.graph.Node
node.element_id              # stable within this transaction only
node.labels                  # frozenset({'Person'})
dict(node)                   # all properties as plain dict

rel  = record["r"]           # neo4j.graph.Relationship
rel.type                     # 'KNOWS'

dt = record["created_at"]    # neo4j.time.DateTime
dt.to_native()               # datetime.datetime (loses sub-µs precision)
```

Full type mapping table → [references/data-types.md](references/data-types.md)

---

## Batch Writes with UNWIND

Pass `list[dict]` — only shape the driver serializes correctly for `UNWIND`.

```python
people = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
driver.execute_query(
    "UNWIND $rows AS row MERGE (p:Person {name: row.name}) SET p.age = row.age",
    rows=people,
    database_="neo4j",
)
```

Custom objects and dataclasses must be converted to `dict` before passing as parameters.

---

## Performance

- Always set `database_` / `database=` — omitting triggers a home-database round-trip per call.
- `execute_read` routes to replicas automatically; use `routing_=RoutingControl.READ` with `execute_query`.
- Batch writes: one `execute_write` callback for the whole list > one tx per item.
- Large results: stream lazily inside `execute_read` callback; `execute_query` is always eager.

Connection pool tuning:
```python
driver = GraphDatabase.driver(URI, auth=AUTH,
    max_connection_pool_size=50,        # default 100
    connection_acquisition_timeout=30,  # seconds to wait for free connection
    max_connection_lifetime=3600,       # seconds; recycles stale connections
    connection_timeout=15,
    keep_alive=True,
)
```

Session exhaustion: each open session holds a connection. Always use `with driver.session(...) as session`.

Full performance patterns → [references/performance.md](references/performance.md)

---

## Common Errors

| Mistake | Fix |
|---|---|
| f-string / `.format()` Cypher params | Use `$param` placeholders always |
| Param name ending with `_` | Pass via `parameters_={"key_": val}` |
| Omitting `database_` | Always set — saves a round-trip every call |
| Returning `Result` from tx callback | Consume to `list` inside callback |
| Side effects in `execute_read/write` callback | Move outside — callback may retry |
| Passing dataclass/Pydantic as param | Convert to `dict` first |
| `UNWIND` with list of objects | `list[dict]` only |
| `record.get()` for absent-key detection | `"key" in record.keys()` for absent; `.get()` returns `None` for both absent and graph null |
| No `.consume()` after `session.run()` | Commit timing undefined; call `.consume()` |
| Sync driver inside asyncio | Use `AsyncGraphDatabase` — sync blocks event loop |
| Async driver created per request | Singleton — create once at startup |
| Leaked sessions | `with driver.session(...) as session` always |
| `json.dumps(record.data())` with node/temporal | Project scalars in Cypher or convert explicitly |
| `result["name"]` on `EagerResult` | Index `result.records[0]["name"]` or unpack `records, _, _ = ...` |
| `Result.single()` returns None for 0 results | It raises — use `single(strict=False)` |
| `@unit_of_work` on lambda | Use named function |
| `Neo4jError` caught before `ConstraintError` | Catch `ConstraintError` first — it's a subclass |
| `neo4j-driver` package name | Package is `neo4j` since v6; `neo4j-driver` deprecated |

---

## References

Load on demand:
- [references/async.md](references/async.md) — full async patterns: managed transactions, result methods, concurrency
- [references/data-types.md](references/data-types.md) — complete Python↔Cypher type mapping, temporal conversion, graph object API, spatial types (CartesianPoint/WGS84Point)
- [references/performance.md](references/performance.md) — connection pool, lazy streaming, threading vs asyncio, bookmarks/causal consistency
- [references/transactions.md](references/transactions.md) — explicit transactions, rollback, commit uncertainty, `unit_of_work` details

Docs:
- https://neo4j.com/docs/python-manual/current/
- https://neo4j.com/docs/api/python-driver/current/

---

## Checklist
- [ ] Package installed as `neo4j` (not `neo4j-driver`)
- [ ] One Driver instance created at startup; shared everywhere
- [ ] `verify_connectivity()` called at startup
- [ ] `database_` / `database=` set on every call
- [ ] `$param` placeholders used — no f-strings or `.format()`
- [ ] Result consumed inside tx callback (not returned raw)
- [ ] Sessions used as context managers (`with driver.session(...) as session`)
- [ ] `ConstraintError` caught before `Neo4jError`
- [ ] `AsyncGraphDatabase` used in asyncio code (not sync driver)
- [ ] Async driver created once at app startup (not per request)
- [ ] Side effects outside `execute_read/write` callbacks
- [ ] UNWIND batches use `list[dict]`
