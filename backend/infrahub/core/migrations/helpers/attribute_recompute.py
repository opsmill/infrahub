from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

import ujson
from infrahub_sdk.template.exceptions import JinjaTemplateError

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core.migrations.helpers.display_label import is_jinja2_template
from infrahub.core.migrations.query.path_details import (
    GetPathDetailsBranchQuery,
    GetPathDetailsDefaultBranch,
)
from infrahub.core.migrations.query.update_attribute_values import UpdateAttributeValuesQuery
from infrahub.core.migrations.shared import get_migration_console

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


console = get_migration_console()

RowFormatter = Callable[[str, list[str | None]], Awaitable[str | None]]


async def format_hfid_row(_node_uuid: str, values: list[str | None]) -> str | None:
    if not values or any(v is None for v in values):
        return None
    return ujson.dumps(values)


def make_display_label_formatter(template: str, variable_names: list[str]) -> RowFormatter:
    # Parse the Jinja template once per kind; the closure reuses it for every row.
    parsed_template: InfrahubJinja2Template | None = (
        InfrahubJinja2Template(template=template) if is_jinja2_template(template) else None
    )

    async def _format(node_uuid: str, values: list[str | None]) -> str | None:
        if not values:
            return None
        if parsed_template is None:
            return values[0] if values[0] is not None else None
        try:
            return await parsed_template.render(variables=dict(zip(variable_names, values, strict=False)))
        except JinjaTemplateError as exc:
            console.log(f"[yellow]Warning: failed to render display_label for node {node_uuid}: {exc}[/yellow]")
            return None

    return _format


async def paginate_read(
    db: InfrahubDatabase,
    branch: Branch,
    schema_kind: str,
    schema_paths: list[SchemaAttributePath],
    batch_size: int,
) -> AsyncIterator[dict[str, list[str | None]]]:
    """Yield each page of node values for `schema_kind` on `branch`."""
    offset = 0
    while True:
        if branch.is_default:
            read_query: (
                GetPathDetailsDefaultBranch | GetPathDetailsBranchQuery
            ) = await GetPathDetailsDefaultBranch.init(
                db=db,
                schema_kind=schema_kind,
                schema_paths=schema_paths,
                offset=offset,
                limit=batch_size,
            )
        else:
            read_query = await GetPathDetailsBranchQuery.init(
                db=db,
                branch=branch,
                schema_kind=schema_kind,
                schema_paths=schema_paths,
                updates_only=False,
                offset=offset,
                limit=batch_size,
            )
        await read_query.execute(db=db)
        values_map = read_query.get_result_map(schema_paths)
        if not values_map:
            return
        yield values_map
        if len(values_map) < batch_size:
            return
        offset += batch_size


async def paginate_recompute(
    db: InfrahubDatabase,
    branch: Branch,
    schema_kind: str,
    schema_paths: list[SchemaAttributePath],
    attribute_schema: AttributeSchema,
    format_row: RowFormatter,
    at: Timestamp,
    batch_size: int,
) -> None:
    """Read every node of `schema_kind` page-by-page, format with `format_row`, and write the non-None results."""
    async for values_map in paginate_read(
        db=db, branch=branch, schema_kind=schema_kind, schema_paths=schema_paths, batch_size=batch_size
    ):
        updates: dict[str, str] = {}
        for node_uuid, values in values_map.items():
            formatted = await format_row(node_uuid, values)
            if formatted is not None:
                updates[node_uuid] = formatted

        if updates:
            update_query = await UpdateAttributeValuesQuery.init(
                db=db,
                branch=branch,
                attribute_schema=attribute_schema,
                values_by_id_map=updates,
                at=at,
            )
            await update_query.execute(db=db)
