# Transactions — Full Reference

## Explicit Transactions

Use when a transaction spans multiple functions or coordinates with external state.

```python
with driver.session(database="neo4j") as session:
    tx = session.begin_transaction()
    try:
        do_part_a(tx)
        do_part_b(tx)
        tx.commit()
    except Exception as e:
        tx.rollback()
        raise

def do_part_a(tx):
    tx.run("CREATE (p:Person {name: $name})", name="Alice")
```

### Rollback Can Raise

`tx.rollback()` is a network call — if the connection is broken, it raises. Don't let it swallow the original exception:

```python
try:
    tx.commit()
except Exception as original:
    try:
        tx.rollback()
    except Exception as rollback_err:
        original.__suppress_context__ = False
        raise rollback_err from original   # chain both exceptions
    raise
```

### Commit Uncertainty

If `tx.commit()` raises a network-level exception, the commit may or may not have succeeded. Design writes as idempotent with `MERGE` and unique constraints so retrying is safe.

## `@unit_of_work` — Timeout & Metadata

Attaches timeout and server metadata to a managed transaction callback.

```python
from neo4j import unit_of_work

@unit_of_work(timeout=5.0, metadata={"app": "myService", "user": user_id})
def get_people(tx):
    return [r["name"] for r in tx.run("MATCH (p:Person) RETURN p.name AS name")]

session.execute_read(get_people)
```

Metadata appears in `SHOW TRANSACTIONS` and server query logs.

### Cannot Decorate Lambdas

```python
# ❌ Syntax error — cannot decorate a lambda inline
session.execute_write(
    @unit_of_work(timeout=5.0)
    lambda tx: tx.run("MERGE (p:Person {name: $name})", name="Alice")
)

# ❌ Also wrong — the original lambda is used, not the wrapped version
fn = lambda tx: tx.run("MERGE (p:Person {name: $name})", name="Alice")
unit_of_work(timeout=5.0)(fn)   # wraps fn, but not reassigned
session.execute_write(fn)       # uses original

# ✅ Named function with decorator
@unit_of_work(timeout=5.0, metadata={"app": "myService"})
def create_person(tx):
    tx.run("MERGE (p:Person {name: $name})", name="Alice")

session.execute_write(create_person)

# ✅ Assign the wrapped lambda explicitly
create_person = unit_of_work(timeout=5.0)(lambda tx: tx.run(
    "MERGE (p:Person {name: $name})", name="Alice"
))
session.execute_write(create_person)
```

Use named functions when timeout or metadata is needed; lambdas are fine for fire-and-forget callbacks.

## Multiple `tx.run()` Calls

Calling `tx.run()` again before the first `Result` is consumed causes the driver to **buffer the first result in memory**. Safe, but can pull large results into RAM unexpectedly.

```python
def multi_query_tx(tx):
    people = [r["name"] for r in tx.run("MATCH (p:Person) RETURN p.name AS name")]
    # first result consumed — safe to issue second query
    for name in people:
        tx.run("MERGE (:Person {name: $name})-[:VISITED]->(:City {name: 'London'})", name=name)
    return len(people)
```

## Retry Safety

`execute_read` / `execute_write` callbacks **may execute more than once** on transient failures — keep them side-effect-free.

```python
# ❌ Side effect fires on every retry
def dangerous_tx(tx):
    requests.post("https://api.example.com/notify")   # fires on every retry
    tx.run("CREATE (p:Person {name: $name})", name="Alice")

# ✅ Database work only; HTTP call made after confirmed success
def safe_tx(tx):
    tx.run("MERGE (p:Person {name: $name})", name="Alice")   # idempotent

session.execute_write(safe_tx)
requests.post("https://api.example.com/notify")   # outside callback
```

## Repository Pattern

```python
from neo4j import Driver, RoutingControl
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int

class PersonRepository:
    def __init__(self, driver: Driver, database: str = "neo4j"):
        self._driver = driver
        self._db = database

    def find_by_name_prefix(self, prefix: str) -> list[Person]:
        records, _, _ = self._driver.execute_query(
            "MATCH (p:Person) WHERE p.name STARTS WITH $prefix RETURN p.name AS name, p.age AS age",
            prefix=prefix,
            routing_=RoutingControl.READ,
            database_=self._db,
        )
        return [Person(name=r["name"], age=r["age"]) for r in records]

    def create(self, person: Person) -> None:
        self._driver.execute_query(
            "CREATE (p:Person {name: $name, age: $age})",
            name=person.name, age=person.age,
            database_=self._db,
        )

    def bulk_create(self, people: list[Person]) -> None:
        rows = [{"name": p.name, "age": p.age} for p in people]
        self._driver.execute_query(
            "UNWIND $rows AS row MERGE (p:Person {name: row.name}) SET p.age = row.age",
            rows=rows,
            database_=self._db,
        )
```
