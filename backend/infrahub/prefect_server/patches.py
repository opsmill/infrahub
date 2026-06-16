from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.server.events import filters

if TYPE_CHECKING:
    import sqlalchemy as sa
    from sqlalchemy import orm


def _is_like_match_expression(
    column: orm.InstrumentedAttribute,
    match_expression: str,
) -> sa.BinaryExpression:
    """Translate a match expression to a SQL LIKE expression with an explicit escape character.

    Upstream Prefect (>=3.6.14, still present in 3.7.4) escapes literal `%` and `_` with a
    backslash but does not declare an ESCAPE character on the LIKE expression. PostgreSQL
    uses backslash as the default LIKE escape so the queries work there, but SQLite has no
    default escape character: label values containing `_` or `%` (such as most Infrahub
    branch names) silently never match. Declaring the escape character explicitly restores
    correct behavior on both databases.
    """
    is_negated = match_expression.startswith("!")

    translation = str.maketrans({"*": "%", "?": "_", "%": "\\%", "_": "\\_"})
    expression = column.like(match_expression.removeprefix("!").translate(translation), escape="\\")

    return ~expression if is_negated else expression


def apply_patches() -> None:
    filters._is_like_match_expression = _is_like_match_expression  # ty: ignore[invalid-assignment]
