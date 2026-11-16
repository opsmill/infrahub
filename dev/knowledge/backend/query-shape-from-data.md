# Queries Whose Shape Depends on a Lookup

> Part of: `dev/knowledge/backend/` | Related: [Query Pattern](query-pattern.md), [Database Schema](database-schema.md)

Some queries have several valid shapes, and the best one depends on something that has to be looked up first: the routes the schema allows between two kinds, or the number of edges on the vertices a filter names. This page covers when to look it up with a small query, where that decision is made, and how to choose the start of a filtered read.

## Run a small query to choose the shape of a large one

When a query is slow for some inputs and fast for others, and no single shape is best for all of them, send a small query first and build the large one from its answer. Do this instead of one statement that holds every shape, and instead of guessing from the schema.

- **The small query must cost almost nothing.** Read stored counts (the degree of a vertex, the number of nodes with a label) or an index. If it has to expand or filter, it costs what it is meant to save.
- **Send one small query per large query.** Put every count the decision needs in the same statement.
- **Keep the previous shape as the default.** Take the new shape only when the answer shows a clear margin, so an input the new shape does not help keeps its text and its plan.
- **Measure the added round trip.** Every call that sends the small query pays for it, including the calls that then keep the previous shape. Skip the small query when the input rules the new shape out.

## Decide first, then build

A `Query` sends nothing to the database while it is built. `__init__` and `query_init` assemble text and parameters, nothing else. When the text depends on a lookup, a separate class does the lookup, decides, and hands the decision to the query. The entry point calls that class.

```python
# ✅ The builder runs the count, the query receives the decision
class NodeGetListQueryBuilder:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def build(self, schema: MainSchemaTypes, branch: Branch, filters: dict[str, Any]) -> NodeGetListQuery:
        query = NodeGetListQuery(schema=schema, branch=branch, filters=filters)
        index_start = await self._select_index_start(node_kind=schema.kind, index_starts=query.get_index_starts())
        await query.query_init(db=self.db, index_start=index_start)
        return query

# ❌ The query runs another query while it builds its own text
class NodeGetListQuery(Query):
    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        count_query = NodeGetListIndexStartQuery(node_kind=self.schema.kind, index_starts=self.get_index_starts())
        await count_query.execute(db=db)
```

What this keeps true:

- Building a query costs no round trip, so a caller that builds one to read or test its text pays nothing.
- The cost of the decision shows at the call site, where it can be skipped or made once for several queries.
- A test can pass each possible decision to the query and compare the results, without arranging data that makes the lookup choose it.

Where the codebase already does this:

- Path traversal: the resolver in `backend/infrahub/graphql/queries/path.py` calls `SchemaPlanner.plan()` and passes the plan to `PathTraversalExecutor` (`backend/infrahub/graph_traversal/executor.py`), which hands it to the queries in `backend/infrahub/graph_traversal/path.py`. None of them calls the planner.
- Filtered list reads: `NodeGetListQueryBuilder` (`backend/infrahub/core/query/node_get_list_builder.py`) runs `NodeGetListIndexStartQuery` and passes the selected start to `NodeGetListQuery`.

## Write Cypher patterns in the query modules

Build the Cypher of a new query in `backend/infrahub/core/query/`, with `QueryNode` and `QueryRel` or as inline text. Do not add a caller of `AttributeSchema.get_query_filter` or `RelationshipSchema.get_query_filter`: they generate Cypher from the schema classes, which ties the schema layer to the query layer, and their return value is a list whose meaning depends on the position of each element.

## Start a filtered read from the filter only when a count shows it reads less

A read that filters a kind on an exact attribute value or on peer ids can start from every node of the kind, or from the indexed vertex of the filter (the value vertex, or the peer). Choose the start per query:

- **Count, do not infer from the schema.** Starting from an indexed vertex reads every edge on it, whatever is at the other end. A value vertex is shared by the attributes of every kind that hold the value, and a peer can relate to most nodes of a kind, so a unique attribute or a cardinality-one relationship says nothing about the cost.
- **Use counts that expand nothing.** `COUNT { ()-[:HAS_VALUE]-(av) }` reads the degree stored on the vertex, and `MATCH (n:<Kind>) RETURN count(n)` reads the count store. Run both in one query. They include deleted nodes and every branch, so use them to compare the two starts, never as a result.
- **Change the start only with a margin.** Start from the vertex with the fewest edges, and only when the kind holds several nodes per edge: following an edge to its node costs more than reading one node of the kind.
- **Let the new start return a superset.** Give its `MATCH` no branch, time or status condition. The filter subqueries that already decide the result run after it, unchanged, so those rules stay in one place.
- **Leave the other path byte-identical.** One statement that holds both starts in a `UNION` changes the text of every query: the planner can plan the previous start differently inside it, and the part that is not used can still scan the kind. With the choice made before the query is built, a query that keeps the previous start keeps its text and its plan.
- **Prove it with each start passed in.** In a test, build the query once per start it can take and compare the returned ids with the expected ones, so the result does not depend on what the count selects. Profile one filter that few nodes match and one that most nodes match.

`build_index_start` and `NodeGetListIndexStartQuery` (`backend/infrahub/core/query/index_start.py`) are the instance to read alongside a new one.
