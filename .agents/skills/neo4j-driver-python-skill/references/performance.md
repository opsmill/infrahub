# Performance & Scalability

## Connection Pool Configuration

```python
driver = GraphDatabase.driver(URI, auth=AUTH,
    max_connection_pool_size=50,        # default 100; tune to workload
    connection_acquisition_timeout=30,  # seconds to wait for free connection
    max_connection_lifetime=3600,       # seconds; recycles stale connections
    connection_timeout=15,              # seconds to establish new connection
    keep_alive=True,                    # TCP keepalive
)
```

Each open session holds a connection. Leaked sessions exhaust the pool — new sessions block until `connection_acquisition_timeout` then raise `ClientError`. Always use `with driver.session(...) as session`.

## Batch Writes — Three Patterns

### UNWIND (best for bulk import)

```python
rows = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
driver.execute_query(
    "UNWIND $rows AS row MERGE (p:Person {name: row.name}) SET p.age = row.age",
    rows=rows, database_="neo4j",
)
```

### Group in one managed transaction

```python
# ❌ One tx per item — high overhead
for item in items:
    driver.execute_query("CREATE (n:Node {id: $id})", id=item["id"], database_="neo4j")

# ✅ One callback for the whole batch
def bulk_create(tx):
    for item in items:
        tx.run("CREATE (n:Node {id: $id})", id=item["id"])

with driver.session(database="neo4j") as session:
    session.execute_write(bulk_create)
```

### CALL IN TRANSACTIONS (very large data — use via session.run, not execute_query)

```cypher
UNWIND $rows AS row
CALL (row) {
  MERGE (p:Person {name: row.name})
} IN TRANSACTIONS OF 1000 ROWS ON ERROR CONTINUE
```

## Lazy vs Eager Loading

```python
# execute_query is always eager — fine for small/medium results
records, _, _ = driver.execute_query("MATCH (p:Person) RETURN p", database_="neo4j")

# Large results — stream lazily inside managed transaction
def process_large_result(tx):
    result = tx.run("MATCH (p:Person) RETURN p.name AS name")
    for record in result:           # one record at a time
        process(record["name"])     # don't build a list

with driver.session(database="neo4j") as session:
    session.execute_read(process_large_result)
```

## Threading vs asyncio

The Python GIL limits CPU parallelism for threads; both threads and asyncio overlap on I/O.

```python
# Sync threading — OK for moderate I/O concurrency
from concurrent.futures import ThreadPoolExecutor

def query(name):
    records, _, _ = driver.execute_query(
        "MATCH (p:Person {name: $name}) RETURN p", name=name, database_="neo4j"
    )
    return records

with ThreadPoolExecutor(max_workers=10) as pool:
    results = list(pool.map(query, names))

# asyncio — preferred for high-concurrency workloads
async def run_all(names):
    tasks = [
        driver.execute_query("MATCH (p:Person {name: $name}) RETURN p",
                              name=name, database_="neo4j")
        for name in names
    ]
    return await asyncio.gather(*tasks)
```

## Causal Consistency & Bookmarks

Within a single session, queries are automatically causally chained. Across sessions — use `execute_query` (shares `BookmarkManager` automatically), or pass bookmarks explicitly:

```python
from neo4j import Bookmarks

with driver.session(database="neo4j") as session_a:
    session_a.execute_write(lambda tx: tx.run("MERGE (p:Person {name: 'Alice'})"))
    bookmarks_a = session_a.last_bookmarks()

with driver.session(database="neo4j") as session_b:
    session_b.execute_write(lambda tx: tx.run("MERGE (p:Person {name: 'Bob'})"))
    bookmarks_b = session_b.last_bookmarks()

combined = Bookmarks.from_raw_values(
    *bookmarks_a.raw_values, *bookmarks_b.raw_values
)

with driver.session(database="neo4j", bookmarks=combined) as session_c:
    session_c.execute_write(
        lambda tx: tx.run("MATCH (a:Person {name:'Alice'}), (b:Person {name:'Bob'}) "
                          "MERGE (a)-[:KNOWS]->(b)")
    )
```

`execute_query` shares a `BookmarkManager` automatically — usually sufficient.
