from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrahub.core.query import Query
    from infrahub.database import InfrahubDatabase


async def explain_plan_operators(db: InfrahubDatabase, query: Query) -> list[str]:
    """Return each operator of the plan Neo4j chooses for the query, as `operatorType: details`."""
    rendered = query.render()
    _, metadata = await db.execute_query_with_metadata(
        query="EXPLAIN\n" + rendered.text, params=rendered.params, name=f"explain_{query.name}"
    )
    return _plan_operators(metadata["plan"])


def _plan_operators(plan: dict[str, Any]) -> list[str]:
    operator = f"{plan.get('operatorType', '')}: {plan.get('args', {}).get('Details', '')}"
    return [operator] + [
        child_operator for child in plan.get("children", []) for child_operator in _plan_operators(child)
    ]
