# Async Driver — Full Reference

## Setup

```python
from neo4j import AsyncGraphDatabase, RoutingControl
import asyncio

URI  = "neo4j+s://xxx.databases.neo4j.io"
AUTH = ("neo4j", "password")

# Singleton — never create per-request
driver = AsyncGraphDatabase.driver(URI, auth=AUTH)
await driver.verify_connectivity()
# on shutdown:
await driver.close()
```

## Async Managed Transactions

```python
async def get_people(tx):
    result = await tx.run("MATCH (p:Person) RETURN p.name AS name")
    return await result.values()   # consume INSIDE callback

async def create_person(tx, name: str):
    await tx.run("MERGE (p:Person {name: $name})", name=name)

async def run_queries(driver):
    async with driver.session(database="neo4j") as session:
        people = await session.execute_read(get_people)
        await session.execute_write(create_person, "Carol")
```

## Async Result Methods

| Method | Returns | Notes |
|---|---|---|
| `await result.values()` | `list[list]` | One inner list per row |
| `await result.data()` | `list[dict]` | One dict per record, keyed by column name |
| `await result.single()` | `Record` | Raises if 0 or 2+ results |
| `await result.single(strict=False)` | `Record \| None` | None for 0, raises for 2+ |
| `await result.fetch(n)` | `list[Record]` | Up to n records |
| `await result.consume()` | `ResultSummary` | Discards remaining |
| `async for record in result` | iterates `Record` | Lazy streaming |

## FastAPI Lifespan Pattern

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from neo4j import AsyncGraphDatabase, RoutingControl

_driver = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _driver
    _driver = AsyncGraphDatabase.driver(URI, auth=AUTH)
    await _driver.verify_connectivity()
    yield
    await _driver.close()

app = FastAPI(lifespan=lifespan)

def get_driver():
    return _driver

@app.get("/people")
async def get_people(driver=Depends(get_driver)):
    records, _, _ = await driver.execute_query(
        "MATCH (p:Person) RETURN p.name AS name",
        database_="neo4j",
        routing_=RoutingControl.READ,
    )
    return [r["name"] for r in records]
```

## Concurrency with asyncio.gather

```python
async def run_concurrent(driver):
    results = await asyncio.gather(
        driver.execute_query("MATCH (a:Artist) RETURN a.name AS name", database_="neo4j"),
        driver.execute_query("MATCH (v:Venue)  RETURN v.name AS name",  database_="neo4j"),
    )
    artists = [r["name"] for r in results[0].records]
    venues  = [r["name"] for r in results[1].records]
```

## Common Async Mistakes

```python
# ❌ Sync driver in asyncio — blocks event loop
async def bad():
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        records, _, _ = driver.execute_query("MATCH (p:Person) RETURN p")

# ✅ Async driver
async def good():
    async with AsyncGraphDatabase.driver(URI, auth=AUTH) as driver:
        records, _, _ = await driver.execute_query("MATCH (p:Person) RETURN p")

# ❌ Async driver created per request — rebuilds connection pool every time
async def handle_request(name: str):
    async with AsyncGraphDatabase.driver(URI, auth=AUTH) as driver:
        records, _, _ = await driver.execute_query("...", database_="neo4j")

# ✅ Singleton at startup
_driver = AsyncGraphDatabase.driver(URI, auth=AUTH)

async def handle_request(name: str):
    records, _, _ = await _driver.execute_query("...", database_="neo4j")
```
