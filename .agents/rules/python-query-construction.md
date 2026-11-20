---
paths:
  - "backend/infrahub/**/*.py"
---

# Query construction

Applies when writing or changing a `Query` class or the code that creates one.

- A `Query` sends nothing to the database while it is built: when its text depends on a lookup, a builder or planner does the lookup and passes the decision to the query.
- Build the text of a new query in `__init__`; `query_init()` is for the older queries that already have one.
- A read that keeps automatic pagination ends with an `ORDER BY` on a unique key, and a read that pages in its own text sorts directly before its `SKIP`/`LIMIT`; without a total order a page can skip or repeat rows.
- Do not add a caller of `AttributeSchema.get_query_filter` or `RelationshipSchema.get_query_filter`; write the Cypher pattern in the query module.

Full reference: `dev/knowledge/backend/query-shape-from-data.md`, `dev/knowledge/backend/query-pattern.md` §"Initialization" and §"Pagination".
