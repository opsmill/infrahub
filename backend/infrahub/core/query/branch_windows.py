"""The read window of every live branch, for queries that need an answer across branches.

A branch reads its own edges and the global branch's edges at the read time, and its origin branch's edges at the
time it branched, capped at the read time. A live branch is any branch but the global one and those being deleted.
The default branch's window has a NULL origin, so a comparison with its origin is never true.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.timestamp import Timestamp

# Written as a literal because importing the branch status enum from here would close an import cycle.
_DELETING_STATUS = "DELETING"


def _render_window(time_param: str) -> str:
    return f"""{{
        name: branch.name,
        origin_name: CASE WHEN branch.is_default THEN NULL ELSE branch.origin_branch END,
        origin_at: CASE
            WHEN branch.is_default THEN NULL
            WHEN branch.branched_from < ${time_param} THEN branch.branched_from
            ELSE ${time_param}
        END
    }}"""


def _render_carry(carry: Sequence[str]) -> str:
    return "".join(f"{variable}, " for variable in carry)


def render_branch_windows_clause(
    *,
    carry: Sequence[str] = (),
    variable_name: str = "branch_windows",
    time_param: str = "windows_at",
    include_deleting: bool = False,
) -> str:
    """Render the clause that collects the window of every live branch into `variable_name`.

    The clause reads `$global_branch_name` and `$<time_param>`. It aggregates every row before it, so it opens the
    query or is preceded only by the variables in `carry`. With `include_deleting`, it also collects the names of the
    branches being deleted into `deleting_branches`.
    """
    window = _render_window(time_param=time_param)
    if not include_deleting:
        return f"""
    MATCH (branch:Branch)
    WHERE branch.name <> $global_branch_name
    AND branch.status <> "{_DELETING_STATUS}"
    WITH {_render_carry(carry=carry)}collect({window}) AS {variable_name}
    """
    return f"""
    MATCH (branch:Branch)
    WHERE branch.name <> $global_branch_name
    WITH {_render_carry(carry=carry)}
        collect(CASE WHEN branch.status <> "{_DELETING_STATUS}" THEN {window} END) AS {variable_name},
        collect(CASE WHEN branch.status = "{_DELETING_STATUS}" THEN branch.name END) AS deleting_branches
    """


def build_branch_windows_query(
    *,
    at: Timestamp,
    enabled: bool,
    carry: Sequence[str] = (),
    variable_name: str = "branch_windows",
    time_param: str = "windows_at",
    include_deleting: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Return the clause that collects the live branch windows, with its parameters.

    When `enabled` is false, the clause sets `variable_name` (and `deleting_branches` with `include_deleting`) to
    NULL and reads no branch, so a read on one branch keeps its query plan.
    """
    if not enabled:
        variables = [*carry, f"NULL AS {variable_name}"]
        if include_deleting:
            variables.append("NULL AS deleting_branches")
        return f"WITH {', '.join(variables)}", {}

    query = render_branch_windows_clause(
        carry=carry, variable_name=variable_name, time_param=time_param, include_deleting=include_deleting
    )
    return query, {time_param: at.to_string(), "global_branch_name": GLOBAL_BRANCH_NAME}


def render_window_filter(*, edge: str, window: str = "window", time_param: str = "windows_at") -> str:
    """Render whether `edge` is visible in the branch window `window`.

    The predicate is false, never NULL, for the default branch's window, so it can be negated or used in a list
    predicate such as `none()`.
    """
    return (
        f"(({edge}.branch IN [$global_branch_name, {window}.name]"
        f" AND {edge}.from <= ${time_param} AND ({edge}.to IS NULL OR {edge}.to > ${time_param}))"
        f" OR ({window}.origin_name IS NOT NULL AND {edge}.branch = {window}.origin_name"
        f" AND {edge}.from <= {window}.origin_at AND ({edge}.to IS NULL OR {edge}.to > {window}.origin_at)))"
    )


def render_outranks(*, edge: str, competitor: str = "r") -> str:
    """Render whether `competitor` is ranked before `edge`: a higher branch level, or the same level and a later start."""
    return (
        f"({competitor}.branch_level > {edge}.branch_level"
        f" OR ({competitor}.branch_level = {edge}.branch_level AND {competitor}.from > {edge}.from))"
    )
