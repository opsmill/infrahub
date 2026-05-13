from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.helpers.attribute_recompute import (
    format_hfid_row,
    make_display_label_formatter,
    paginate_recompute,
)
from infrahub.core.migrations.helpers.display_label import extract_jinja2_variables, is_jinja2_template
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

NORMALIZED_KINDS = {"IPHost", "IPNetwork"}


def _path_uses_ip(schema_path: SchemaAttributePath) -> bool:
    return bool(schema_path.attribute_schema and schema_path.attribute_schema.kind in NORMALIZED_KINDS)


def _extract_display_label_schema_paths(
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
class _RecomputePlan:
    schema: NodeSchema | ProfileSchema | TemplateSchema
    hfid_paths: list[SchemaAttributePath] | None = None
    display_label_paths: list[SchemaAttributePath] | None = None


def _hfid_paths_if_affected(
    schema: NodeSchema | ProfileSchema | TemplateSchema,
    schema_branch: SchemaBranch,
    branch_filter: tuple[BranchSupportType, ...],
) -> list[SchemaAttributePath] | None:
    if not schema.human_friendly_id:
        return None
    paths = [schema.parse_schema_path(path=str(p), schema=schema_branch) for p in schema.human_friendly_id]
    has_relevant_ip_attr = any(
        _path_uses_ip(p) and p.attribute_schema and p.attribute_schema.get_branch() in branch_filter for p in paths
    )
    return paths if has_relevant_ip_attr else None


def _display_label_paths_if_affected(
    schema: NodeSchema | ProfileSchema | TemplateSchema,
    schema_branch: SchemaBranch,
    branch_filter: tuple[BranchSupportType, ...],
) -> list[SchemaAttributePath] | None:
    paths = _extract_display_label_schema_paths(schema, schema_branch)
    has_relevant_ip_attr = any(
        _path_uses_ip(p) and p.attribute_schema and p.attribute_schema.get_branch() in branch_filter for p in paths
    )
    return paths if has_relevant_ip_attr else None


def _collect_plans(
    schema_branch: SchemaBranch, branch_filter: tuple[BranchSupportType, ...]
) -> dict[str, _RecomputePlan]:
    plans: dict[str, _RecomputePlan] = {}
    for node_schema_name in schema_branch.node_names:
        if node_schema_name in SCHEMA_KINDS_TO_SKIP:
            continue
        schema = schema_branch.get_node(name=node_schema_name, duplicate=False)
        hfid_paths = _hfid_paths_if_affected(schema, schema_branch, branch_filter)
        display_label_paths = _display_label_paths_if_affected(schema, schema_branch, branch_filter)
        if hfid_paths or display_label_paths:
            plans[node_schema_name] = _RecomputePlan(
                schema=schema, hfid_paths=hfid_paths, display_label_paths=display_label_paths
            )
    return plans


class Migration071(MigrationRequiringRebase):
    """Recompute hfid/display_label for any schema that depends on an IPHost or IPNetwork attribute,
    so derived values match the canonical form stored on the attribute."""

    name: str = "071_recompute_hfid_for_ip_attributes"
    minimum_version: int = 70
    update_batch_size: int = 1000

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _execute_plan(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        plan: _RecomputePlan,
        hfid_attribute_schema: AttributeSchema,
        display_label_attribute_schema: AttributeSchema,
        at: Timestamp,
    ) -> None:
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
            for kind, plan in plans.items():
                console.log(f"Recomputing HFID/display_label for {kind}")
                await self._execute_plan(
                    db=db,
                    branch=branch,
                    plan=plan,
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
            branch_filter=(BranchSupportType.AWARE, BranchSupportType.AGNOSTIC, BranchSupportType.LOCAL),
        )

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        return await self._run(
            db=migration_input.db,
            branch=branch,
            at=migration_input.at,
            branch_filter=(BranchSupportType.AWARE, BranchSupportType.LOCAL),
        )
