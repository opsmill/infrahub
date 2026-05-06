from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import netaddr
import ujson
from infrahub_sdk.template.exceptions import JinjaTemplateError

from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.helpers.display_label import (
    extract_jinja2_variables,
    is_jinja2_template,
    render_display_label,
)
from infrahub.core.migrations.query.path_details import (
    SCHEMA_KINDS_TO_SKIP,
    GetPathDetailsBranchQuery,
    GetPathDetailsDefaultBranch,
)
from infrahub.core.migrations.query.update_attribute_values import UpdateAttributeValuesQuery
from infrahub.core.migrations.shared import (
    MigrationInput,
    MigrationRequiringRebase,
    MigrationResult,
    get_migration_console,
)

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, NodeSchema, ProfileSchema, TemplateSchema
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


console = get_migration_console()

_MAC_KIND = "MacAddress"
_RowFormatter = Callable[[str, list[str | None]], Awaitable[str | None]]


def _to_colon_form(value: str) -> str:
    """Convert any valid MAC representation to colon-uppercase (AA:BB:CC:DD:EE:FF)."""
    return netaddr.EUI(addr=value).format(dialect=netaddr.mac_unix_expanded).upper()


def _path_uses_mac(schema_path: SchemaAttributePath) -> bool:
    return bool(schema_path.attribute_schema and schema_path.attribute_schema.kind == _MAC_KIND)


def _extract_display_label_paths(
    schema: NodeSchema | ProfileSchema | TemplateSchema,
    schema_branch: SchemaBranch,
) -> list[SchemaAttributePath]:
    if not schema.display_label:
        return []
    if not is_jinja2_template(schema.display_label):
        return [schema.parse_schema_path(path=schema.display_label, schema=schema_branch)]
    return [
        schema.parse_schema_path(path=variable, schema=schema_branch)
        for variable in extract_jinja2_variables(schema.display_label)
    ]


def _hfid_paths_if_mac(
    schema: NodeSchema | ProfileSchema | TemplateSchema, schema_branch: SchemaBranch
) -> list[SchemaAttributePath] | None:
    if not schema.human_friendly_id:
        return None
    paths = [schema.parse_schema_path(path=str(p), schema=schema_branch) for p in schema.human_friendly_id]
    return paths if any(_path_uses_mac(p) for p in paths) else None


def _display_label_paths_if_mac(
    schema: NodeSchema | ProfileSchema | TemplateSchema, schema_branch: SchemaBranch
) -> list[SchemaAttributePath] | None:
    paths = _extract_display_label_paths(schema, schema_branch)
    return paths if paths and any(_path_uses_mac(p) for p in paths) else None


@dataclass
class _MacPlan:
    schema: NodeSchema | ProfileSchema | TemplateSchema
    mac_attributes: list[AttributeSchema]
    hfid_paths: list[SchemaAttributePath] | None
    display_label_paths: list[SchemaAttributePath] | None


def _collect_plans(schema_branch: SchemaBranch, branch_filter: tuple[BranchSupportType, ...]) -> list[_MacPlan]:
    plans: list[_MacPlan] = []
    for node_schema_name in schema_branch.node_names:
        if node_schema_name in SCHEMA_KINDS_TO_SKIP:
            continue
        schema = schema_branch.get_node(name=node_schema_name, duplicate=False)
        if schema.branch not in branch_filter:
            continue
        mac_attrs = [a for a in schema.attributes if a.kind == _MAC_KIND]
        if not mac_attrs:
            continue
        plans.append(
            _MacPlan(
                schema=schema,
                mac_attributes=mac_attrs,
                hfid_paths=_hfid_paths_if_mac(schema, schema_branch),
                display_label_paths=_display_label_paths_if_mac(schema, schema_branch),
            )
        )
    return plans


async def _format_hfid(_node_uuid: str, values: list[str | None]) -> str | None:
    if not values or any(v is None for v in values):
        return None
    return ujson.dumps(values)


def _make_display_label_formatter(template: str, variable_names: list[str]) -> _RowFormatter:
    async def _format(node_uuid: str, values: list[str | None]) -> str | None:
        if not values:
            return None
        try:
            return await render_display_label(display_label=template, variable_names=variable_names, values=values)
        except JinjaTemplateError as exc:
            console.log(f"[yellow]Warning: failed to render display_label for node {node_uuid}: {exc}[/yellow]")
            return None

    return _format


class Migration070(MigrationRequiringRebase):
    """
    Normalize stored `MacAddress` attribute values to colon-separated EUI-48
    form (`AA:BB:CC:DD:EE:FF`) per issue #9015.

    Pre-existing values may be in any form accepted by ``netaddr.EUI`` — on
    `stable`, ``serialize_value`` produces dash-uppercase form, but
    ``_to_colon_form()`` accepts any valid MAC representation and re-emits
    colon form, so input variation is handled. This migration:

    1. Rewrites every stored `MacAddress` attribute value to colon form.
    2. Rebuilds `human_friendly_id` and `display_label` for every schema that
       references a MAC attribute, so derived attributes follow the new value.
    """

    name: str = "070_normalize_mac_address_values_to_colon"
    minimum_version: int = 69
    update_batch_size: int = 1000

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _read_path_values(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema_kind: str,
        schema_paths: list[SchemaAttributePath],
        offset: int,
    ) -> dict[str, list[str | None]]:
        query: GetPathDetailsDefaultBranch | GetPathDetailsBranchQuery
        if branch.is_default:
            query = await GetPathDetailsDefaultBranch.init(
                db=db,
                schema_kind=schema_kind,
                schema_paths=schema_paths,
                offset=offset,
                limit=self.update_batch_size,
            )
        else:
            query = await GetPathDetailsBranchQuery.init(
                db=db,
                branch=branch,
                schema_kind=schema_kind,
                schema_paths=schema_paths,
                updates_only=False,
                offset=offset,
                limit=self.update_batch_size,
            )
        await query.execute(db=db)
        return query.get_result_map(schema_paths)

    async def _paginate(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema_kind: str,
        schema_paths: list[SchemaAttributePath],
        attribute_schema: AttributeSchema,
        format_row: _RowFormatter,
        at: Timestamp,
    ) -> None:
        offset = 0
        while True:
            values_map = await self._read_path_values(
                db=db, branch=branch, schema_kind=schema_kind, schema_paths=schema_paths, offset=offset
            )
            num_results = len(values_map)
            if num_results == 0:
                break

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

            if num_results < self.update_batch_size:
                break
            offset += self.update_batch_size

    async def _convert_mac_attribute(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema: NodeSchema | ProfileSchema | TemplateSchema,
        schema_branch: SchemaBranch,
        attribute_schema: AttributeSchema,
        at: Timestamp,
    ) -> None:
        path = schema.parse_schema_path(path=f"{attribute_schema.name}__value", schema=schema_branch)

        async def format_row(node_uuid: str, values: list[str | None]) -> str | None:
            if not values or values[0] is None:
                return None
            old = values[0]
            try:
                new = _to_colon_form(old)
            except (netaddr.AddrFormatError, ValueError) as exc:
                console.log(
                    f"[yellow]Skipping node {node_uuid} on {schema.kind}.{attribute_schema.name}: "
                    f"value {old!r} is not a valid MAC ({exc})[/yellow]"
                )
                return None
            return new if new != old else None

        await self._paginate(
            db=db,
            branch=branch,
            schema_kind=schema.kind,
            schema_paths=[path],
            attribute_schema=attribute_schema,
            format_row=format_row,
            at=at,
        )

    async def _execute_plan(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        plan: _MacPlan,
        schema_branch: SchemaBranch,
        hfid_attribute_schema: AttributeSchema,
        display_label_attribute_schema: AttributeSchema,
        at: Timestamp,
    ) -> None:
        for attr in plan.mac_attributes:
            console.log(f"Normalizing MacAddress values for {plan.schema.kind}.{attr.name}")
            await self._convert_mac_attribute(
                db=db, branch=branch, schema=plan.schema, schema_branch=schema_branch, attribute_schema=attr, at=at
            )

        if plan.hfid_paths:
            await self._paginate(
                db=db,
                branch=branch,
                schema_kind=plan.schema.kind,
                schema_paths=plan.hfid_paths,
                attribute_schema=hfid_attribute_schema,
                format_row=_format_hfid,
                at=at,
            )
        if plan.display_label_paths and plan.schema.display_label:
            variable_names = [s.attribute_path_as_str for s in plan.display_label_paths]
            await self._paginate(
                db=db,
                branch=branch,
                schema_kind=plan.schema.kind,
                schema_paths=plan.display_label_paths,
                attribute_schema=display_label_attribute_schema,
                format_row=_make_display_label_formatter(plan.schema.display_label, variable_names),
                at=at,
            )

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at

        root_node = await get_root_node(db=db, initialize=False)
        default_branch = await Branch.get_by_name(db=db, name=root_node.default_branch)
        schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)

        plans = _collect_plans(schema_branch, branch_filter=(BranchSupportType.AWARE,))
        if not plans:
            return MigrationResult()

        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")

        try:
            for plan in plans:
                await self._execute_plan(
                    db=db,
                    branch=default_branch,
                    plan=plan,
                    schema_branch=schema_branch,
                    hfid_attribute_schema=hfid_attribute_schema,
                    display_label_attribute_schema=display_label_attribute_schema,
                    at=at,
                )
        except Exception as exc:
            return MigrationResult(errors=[str(exc) or f"{type(exc).__name__}: {repr(exc)}"])

        return MigrationResult()

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)

        plans = _collect_plans(schema_branch, branch_filter=(BranchSupportType.AWARE, BranchSupportType.LOCAL))
        if not plans:
            return MigrationResult()

        base_node_schema = schema_branch.get("SchemaNode", duplicate=False)
        hfid_attribute_schema = base_node_schema.get_attribute("human_friendly_id")
        display_label_attribute_schema = base_node_schema.get_attribute("display_label")

        try:
            for plan in plans:
                await self._execute_plan(
                    db=db,
                    branch=branch,
                    plan=plan,
                    schema_branch=schema_branch,
                    hfid_attribute_schema=hfid_attribute_schema,
                    display_label_attribute_schema=display_label_attribute_schema,
                    at=at,
                )
        except Exception as exc:
            return MigrationResult(errors=[str(exc) or f"{type(exc).__name__}: {repr(exc)}"])

        return MigrationResult()
