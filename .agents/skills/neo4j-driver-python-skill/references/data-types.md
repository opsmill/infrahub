# Data Types — Python ↔ Cypher Mapping

## Parameter Types (allowed)

| Python type | Cypher type |
|---|---|
| `str` | String |
| `int` | Integer |
| `float` | Float |
| `bool` | Boolean |
| `list` / `tuple` | List |
| `dict` | Map |
| `None` | null |
| `datetime.date` | Date |
| `datetime.datetime` | DateTime |
| `datetime.time` | Time |
| `datetime.timedelta` | Duration |
| `neo4j.time.*` types | Corresponding Cypher temporal |

Custom classes, dataclasses, Pydantic models, and enums are **not** auto-serialized — convert to `dict` or primitives first.

```python
from dataclasses import dataclass, asdict

@dataclass
class Person:
    name: str
    age: int

p = Person("Alice", 30)

# ❌ Fails
driver.execute_query("CREATE (p:Person $props)", props=p, database_="neo4j")

# ✅ Convert to dict
driver.execute_query("CREATE (p:Person $props)", props=asdict(p), database_="neo4j")
```

## Graph Object API

```python
# Node — neo4j.graph.Node
node = record["p"]
node.element_id        # stable within this transaction; don't use across transactions
node.labels            # frozenset({'Person'})
node["name"]           # property access by key
dict(node)             # all properties as plain dict

# Relationship — neo4j.graph.Relationship
rel = record["r"]
rel.type               # 'KNOWS'
rel.start_node.element_id
rel.end_node.element_id
rel["since"]           # property
dict(rel)              # all properties as plain dict
```

## Temporal Types

```python
from neo4j.time import DateTime, Date, Time, Duration

dt = record["created_at"]   # neo4j.time.DateTime
dt.to_native()              # datetime.datetime — loses sub-microsecond precision
str(dt)                     # ISO 8601 string — JSON-safe

# Pass Python datetime as a parameter — driver converts automatically
from datetime import datetime, timezone
driver.execute_query("CREATE (e:Event {at: $ts})", ts=datetime.now(timezone.utc), database_="neo4j")

# Duration — access .days / .months (not .inDays / .inMonths)
dur = record["tenure"]      # neo4j.time.Duration
dur.days
dur.months
```

## JSON Serialization

`record.data()` returns a `dict` but `Node`, `Relationship`, `Path`, and `neo4j.time.*` values are still driver objects — not JSON-safe.

```python
# ❌ Raises TypeError if result contains node/rel/temporal
json.dumps(records[0].data())

# ✅ Project scalars in Cypher
records, _, _ = driver.execute_query(
    "MATCH (p:Person) RETURN p.name AS name, p.age AS age, toString(p.created_at) AS created_at",
    database_="neo4j",
)
json.dumps(records[0].data())   # safe — all scalars

# ✅ Extract node properties manually
node = records[0]["p"]
props = dict(node)              # plain dict — json-safe if all property types are primitives
```

## Spatial Types

```python
from neo4j.spatial import CartesianPoint, WGS84Point

# 2D Cartesian (SRID 7203)
pt2d = CartesianPoint((1.23, 4.56))
print(pt2d.x, pt2d.y, pt2d.srid)   # 1.23, 4.56, 7203

# 3D Cartesian (SRID 9157)
pt3d = CartesianPoint((1.23, 4.56, 7.89))
x, y, z = pt3d   # destructuring

# 2D WGS-84 (SRID 4326)
ldn = WGS84Point((-0.118092, 51.509865))
print(ldn.longitude, ldn.latitude, ldn.srid)   # -0.118092, 51.509865, 4326

# 3D WGS-84 (SRID 4979)
shard = WGS84Point((-0.086500, 51.504501, 310))
longitude, latitude, height = shard

# Distance (same SRID only — returns None if SRIDs differ)
records, _, _ = driver.execute_query(
    "RETURN point.distance($p1, $p2) AS distance",
    p1=CartesianPoint((1, 1)), p2=CartesianPoint((10, 10)),
    database_="neo4j",
)
distance = records[0]["distance"]   # float64
```

Pass points as parameters — serialized automatically. Read back via destructuring or `.x`/`.y`/`.z`.

## Null Safety

| Situation | `record["key"]` | `record.get("key")` |
|---|---|---|
| Key present, value non-null | value | value |
| Key present, value is graph null | `None` | `None` |
| Key absent (typo / not in RETURN) | `KeyError` | `None` |

`.get()` cannot distinguish absent key from graph null — use `"key" in record.keys()` when the distinction matters.

```python
# Optional column from OPTIONAL MATCH
if "city" in record.keys() and record["city"] is not None:
    city = record["city"]
else:
    city = "Unknown"
```
