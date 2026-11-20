from typing import Any


def plan_operators(plan: dict[str, Any]) -> list[str]:
    """Flatten an `EXPLAIN` or `PROFILE` plan into one `"<operator>: <details>"` line per operator, root first."""
    operator = f"{plan.get('operatorType', '')}: {plan.get('args', {}).get('Details', '')}"
    return [operator] + [
        child_operator for child in plan.get("children", []) for child_operator in plan_operators(child)
    ]
