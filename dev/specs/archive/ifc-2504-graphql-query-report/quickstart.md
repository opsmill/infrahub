# Developer Quickstart: GraphQL Query Report Introspection

**Feature**: IFC-2504 | **Branch**: `ifc-2504-graphql-query-report`

## What to build

One new file and three targeted edits:

| Action | File |
|--------|------|
| **Create** | `backend/infrahub/graphql/queries/graphql_query_report.py` |
| **Edit** | `backend/infrahub/graphql/queries/__init__.py` |
| **Edit** | `backend/infrahub/graphql/schema.py` |
| **Create** | `backend/tests/component/graphql/queries/test_graphql_query_report.py` |
| **Create** | `changelog/[IFC-2504-number].added.md` |

---

## Step 1 — Create the resolver file

Model after `backend/infrahub/graphql/queries/status.py`.

```python
# backend/infrahub/graphql/queries/graphql_query_report.py
from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, Field, ObjectType, String
from graphql import GraphQLError, GraphQLSyntaxError

from infrahub.core import registry
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo
    from infrahub.graphql.initialization import GraphqlContext


class GraphQLQueryReport(ObjectType):
    targets_unique_nodes = Field(
        Boolean,
        required=True,
        description=(
            "True if every operation resolves to uniquely identifiable nodes "
            "(via required ids argument or uniqueness constraint field). "
            "When true, Infrahub limits artifact regeneration to changed nodes only."
        ),
    )


async def resolve_graphql_query_report(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    query: str,
) -> dict:
    graphql_context: GraphqlContext = info.context
    branch = graphql_context.branch
    schema_branch = registry.schema.get_schema_branch(name=branch.name)

    try:
        analyzer = InfrahubGraphQLQueryAnalyzer(
            query=query,
            schema=info.schema,
            branch=branch,
            schema_branch=schema_branch,
        )
    except GraphQLSyntaxError as exc:
        raise GraphQLError(str(exc)) from exc

    is_valid, errors = analyzer.is_valid
    if not is_valid:
        raise GraphQLError(str(errors))

    return {"targets_unique_nodes": analyzer.query_report.only_has_unique_targets}


InfrahubGraphQLQueryReport = Field(
    GraphQLQueryReport,
    query=String(required=True, description="The raw GraphQL query string to analyze."),
    description="Analyze a GraphQL query string and report how Infrahub will interpret it.",
    resolver=resolve_graphql_query_report,
    required=True,
)
```

## Step 2 — Export from `__init__.py`

```python
# Add to backend/infrahub/graphql/queries/__init__.py
from .graphql_query_report import InfrahubGraphQLQueryReport

# Add to __all__
"InfrahubGraphQLQueryReport",
```

## Step 3 — Register in `schema.py`

```python
# In InfrahubBaseQuery in backend/infrahub/graphql/schema.py
# Add alongside InfrahubStatus:
from .queries import (
    ...,
    InfrahubGraphQLQueryReport,
    ...,
)

class InfrahubBaseQuery(ObjectType):
    ...
    InfrahubGraphQLQueryReport = InfrahubGraphQLQueryReport
```

## Step 4 — Write component tests

File: `backend/tests/component/graphql/queries/test_graphql_query_report.py`

Key fixtures: `db`, `default_branch`, `car_person_schema` (provides `TestCar` with known uniqueness), `prepare_graphql_params`.

Test matrix:

| Test | Query | Expected |
|------|-------|----------|
| `test_targets_unique_nodes_true_ids` | Query with required `ids` arg | `targets_unique_nodes: true` |
| `test_targets_unique_nodes_false_no_filter` | Query for all nodes, no filter | `targets_unique_nodes: false` |
| `test_targets_unique_nodes_true_uniqueness_constraint` | Query with uniqueness constraint field as required arg | `targets_unique_nodes: true` |
| `test_error_empty_query` | `""` | GraphQL error |
| `test_error_invalid_syntax` | `"not graphql {"` | GraphQL error |
| `test_error_nonexistent_type` | `{ NonExistentType123 { id } }` | GraphQL error |

Execute tests directly:
```bash
uv run pytest backend/tests/component/graphql/queries/test_graphql_query_report.py -v
```

## Step 5 — Add changelog fragment

```bash
# File: changelog/[IFC-number].added.md
Added InfrahubGraphQLQueryReport introspection query to report whether a GraphQL query targets unique nodes for artifact regeneration.
```

## Verification

```bash
uv run invoke format
uv run invoke lint
uv run pytest backend/tests/component/graphql/queries/test_graphql_query_report.py -v
```
