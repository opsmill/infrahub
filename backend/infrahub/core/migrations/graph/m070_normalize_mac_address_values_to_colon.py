from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import netaddr

from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.helpers.display_label import extract_jinja2_variables, is_jinja2_template
from infrahub.core.migrations.helpers.recompute import (
    format_hfid_row,
    make_display_label_formatter,
    paginate_recompute,
)
from infrahub.core.migrations.query.path_details import SCHEMA_KINDS_TO_SKIP
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


def _to_colon_form(value: str) -> str:
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

        hfid_paths: list[SchemaAttributePath] | None = None
        if schema.human_friendly_id:
            paths = [schema.parse_schema_path(path=str(p), schema=schema_branch) for p in schema.human_friendly_id]
            if any(_path_uses_mac(p) for p in paths):
                hfid_paths = paths

        display_label_paths: list[SchemaAttributePath] | None = None
        dl_paths = _extract_display_label_paths(schema, schema_branch)
        if dl_paths and any(_path_uses_mac(p) for p in dl_paths):
            display_label_paths = dl_paths

        plans.append(
            _MacPlan(
                schema=schema,
                mac_attributes=mac_attrs,
                hfid_paths=hfid_paths,
                display_label_paths=display_label_paths,
            )
        )
    return plans


class Migration070(MigrationRequiringRebase):
    """Rewrite stored MacAddress attribute values to colon-uppercase form and recompute hfid/display_label
    for any schema that depends on a MacAddress attribute."""

    name: str = "070_normalize_mac_address_values_to_colon"
    minimum_version: int = 69
    update_batch_size: int = 1000

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

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

        await paginate_recompute(
            db=db,
            branch=branch,
            schema_kind=schema.kind,
            schema_paths=[path],
            attribute_schema=attribute_schema,
            format_row=format_row,
            at=at,
            batch_size=self.update_batch_size,
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
            await paginate_recompute(
                db=db,
                branch=branch,
                schema_kind=plan.schema.kind,
                schema_paths=plan.hfid_paths,
                attribute_schema=hfid_attribute_schema,
                format_row=format_hfid_row,
                at=at,
                batch_size=self.update_batch_size,
            )
        if plan.display_label_paths and plan.schema.display_label:
            variable_names = [s.attribute_path_as_str for s in plan.display_label_paths]
            await paginate_recompute(
                db=db,
                branch=branch,
                schema_kind=plan.schema.kind,
                schema_paths=plan.display_label_paths,
                attribute_schema=display_label_attribute_schema,
                format_row=make_display_label_formatter(plan.schema.display_label, variable_names),
                at=at,
                batch_size=self.update_batch_size,
            )

    async def _run(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp,
        branch_filter: tuple[BranchSupportType, ...],
    ) -> MigrationResult:
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)
        plans = _collect_plans(schema_branch, branch_filter=branch_filter)
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

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        root_node = await get_root_node(db=migration_input.db, initialize=False)
        default_branch = await Branch.get_by_name(db=migration_input.db, name=root_node.default_branch)
        return await self._run(
            db=migration_input.db,
            branch=default_branch,
            at=migration_input.at,
            branch_filter=(BranchSupportType.AWARE,),
        )

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        return await self._run(
            db=migration_input.db,
            branch=branch,
            at=migration_input.at,
            branch_filter=(BranchSupportType.AWARE, BranchSupportType.LOCAL),
        )
