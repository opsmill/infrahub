from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.migrations.graph.load_schema_branch import get_or_load_schema_branch
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import NodeSchema, SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.lock import initialize_lock

from .queries import AttributeHealDetectionQuery
from .repairers import MissingRows

if TYPE_CHECKING:
    from rich.console import Console

    from infrahub.core.branch import Branch
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

    from .repairers import MissingRowRepairer


async def ensure_runtime_context(db: InfrahubDatabase) -> None:
    """Prepare the pieces of global state the repair machinery relies on.

    The lock registry backs pool allocations, and the schema manager needs the
    internal schema (to load each branch's schema from the database) plus the
    core models (for pool lookups) — both registerable from memory. The
    node-class mapping makes pool nodes hydrate as allocation-capable objects.
    Everything is already initialized when running inside the server; this
    guard covers the upgrade command and direct invocations.

    Registering a schema from memory stores it under the default branch's name,
    which would make every later lookup of the default branch's schema return
    those core models instead of reading the database — leaving the audit blind
    to user-defined kinds. The database's schema is therefore merged into that
    entry here. It has to be a merge rather than a replacement: loading a schema
    from the database is itself driven by the internal schema, so an entry rebuilt
    from the query alone would drop what a later branch load depends on.
    """
    if lock.registry is None:
        initialize_lock()
    if not registry.schema_has_been_initialized():
        schema_manager = SchemaManager()
        registry.schema = schema_manager
        schema_manager.register_schema(schema=SchemaRoot(**internal_schema))
        schema_manager.register_schema(schema=SchemaRoot(**core_models))
        default_branch = await registry.get_branch(db=db, branch=registry.default_branch)
        schema_manager.set_schema_branch(
            name=default_branch.name,
            schema=await schema_manager.load_schema_from_db(
                db=db,
                branch=default_branch,
                schema=schema_manager.get_schema_branch(name=default_branch.name).duplicate(),
            ),
        )
    if InfrahubKind.NUMBERPOOL not in registry.node:
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


class MissingAttributeRowHealer:
    """Detect and repair the missing generic-inherited attribute rows of a branch.

    The audit covers exactly the attributes a kind inherits from its generics that
    one of the repairers supports — the only rows this damage shape can affect —
    using each branch's processed schema, so an attribute defined by several
    generics is healed with the same effective definition the runtime write path
    uses. Profile and template instances of each kind are audited and repaired
    alongside concrete instances, restricted to the attributes they support.

    With a baseline schema, only kinds whose supported inherited attributes go
    beyond the baseline are audited: rows exist for every attribute the baseline
    defined — the runtime write path and the baseline's own heal guarantee it — so
    only attributes beyond the baseline can be missing. That covers nodes created
    on the branch too: a branch forked after the baseline gained the inheritance
    creates nodes from a schema that already carries it, so every row is written
    at creation; a branch forked before adopts the inheritance at rebase, where
    schema migrations create the rows for the branch's own nodes.
    """

    def __init__(self, db: InfrahubDatabase, console: Console, repairers: list[MissingRowRepairer]) -> None:
        self.db = db
        self.console = console
        self.repairers = repairers

    async def heal(
        self, branch: Branch, at: Timestamp, user_id: str, baseline_schema: SchemaBranch | None = None
    ) -> MigrationResult:
        """Repair every damaged pair of the branch; stop at the first attribute whose repair fails."""
        result = MigrationResult()

        audited_schemas = await self._audited_node_schemas(branch=branch, baseline_schema=baseline_schema)
        self.console.log(f"  Branch {branch.name}: auditing {len(audited_schemas)} kind(s) with inherited attributes")

        repaired_kinds = 0
        for index, node_schema in enumerate(audited_schemas, start=1):
            inherited_attributes = self._supported_inherited_attributes(node_schema=node_schema)
            damaged_uuids_by_attribute = await self._detect_kind_damage(
                branch=branch, node_schema=node_schema, attributes=inherited_attributes
            )
            if not damaged_uuids_by_attribute:
                continue

            pair_count = sum(len(uuids) for uuids in damaged_uuids_by_attribute.values())
            node_count = len({uuid for uuids in damaged_uuids_by_attribute.values() for uuid in uuids})
            self.console.log(
                f"  ({index}/{len(audited_schemas)}) {node_schema.kind}: {pair_count} missing attribute "
                f"row(s) across {node_count} node(s); repairing"
            )

            kind_result = await self._repair_kind(
                branch=branch,
                node_schema=node_schema,
                attributes=[
                    attribute for attribute in inherited_attributes if attribute.name in damaged_uuids_by_attribute
                ],
                damaged_uuids_by_attribute=damaged_uuids_by_attribute,
                at=at,
                user_id=user_id,
            )
            result.errors.extend(kind_result.errors)
            result.nbr_migrations_executed += kind_result.nbr_migrations_executed
            repaired_kinds += 1
            if result.errors:
                break

        if repaired_kinds:
            self.console.log(
                f"  Branch {branch.name}: repaired {result.nbr_migrations_executed} attribute row(s) "
                f"across {repaired_kinds} kind(s)"
            )
        else:
            self.console.log(f"  No missing attribute rows detected on branch {branch.name}; nothing to repair.")

        return result

    async def detect_remaining_damage(self, branch: Branch, baseline_schema: SchemaBranch | None = None) -> list[str]:
        """Return one error per kind still carrying damaged pairs on the branch."""
        errors: list[str] = []
        for node_schema in await self._audited_node_schemas(branch=branch, baseline_schema=baseline_schema):
            damaged_uuids_by_attribute = await self._detect_kind_damage(
                branch=branch,
                node_schema=node_schema,
                attributes=self._supported_inherited_attributes(node_schema=node_schema),
            )
            if not damaged_uuids_by_attribute:
                continue
            node_uuids = {node_uuid for uuids in damaged_uuids_by_attribute.values() for node_uuid in uuids}
            pair_count = sum(len(uuids) for uuids in damaged_uuids_by_attribute.values())
            errors.append(
                f"{node_schema.kind}: {pair_count} missing attribute row(s) across {len(node_uuids)} node(s) "
                f"on branch {branch.name} (attributes: {', '.join(sorted(damaged_uuids_by_attribute))})"
            )
        return errors

    async def _audited_node_schemas(
        self, branch: Branch, baseline_schema: SchemaBranch | None = None
    ) -> list[NodeSchema]:
        schema_branch = await get_or_load_schema_branch(db=self.db, branch=branch)
        audited: list[NodeSchema] = []
        for name in sorted(schema_branch.node_names):
            node_schema = schema_branch.get(name=name, duplicate=False)
            if not isinstance(node_schema, NodeSchema):
                continue
            inherited = self._supported_inherited_attributes(node_schema=node_schema)
            if not inherited:
                continue
            if baseline_schema is not None and not self._inherits_beyond_baseline(
                node_schema=node_schema, inherited=inherited, baseline_schema=baseline_schema
            ):
                continue
            audited.append(node_schema)
        return audited

    def _inherits_beyond_baseline(
        self, node_schema: NodeSchema, inherited: list[AttributeSchema], baseline_schema: SchemaBranch
    ) -> bool:
        if node_schema.kind not in baseline_schema.node_names:
            return True
        baseline_node = baseline_schema.get(name=node_schema.kind, duplicate=False)
        return not {attribute.name for attribute in inherited} <= set(baseline_node.attribute_names)

    def _supported_inherited_attributes(self, node_schema: NodeSchema) -> list[AttributeSchema]:
        return sorted(
            (
                attribute
                for attribute in node_schema.attributes
                if attribute.inherited and any(repairer.supports(attribute) for repairer in self.repairers)
            ),
            key=lambda attribute: attribute.name,
        )

    def _audit_scopes(
        self, node_schema: NodeSchema, attributes: list[AttributeSchema]
    ) -> list[tuple[str, list[AttributeSchema]]]:
        """Pair each audited instance kind with the attributes its instances must carry.

        Profile and template instances gain an attribute only when it passes the same
        support predicates that gate row creation on them.
        """
        profile_attributes: list[AttributeSchema] = []
        template_attributes: list[AttributeSchema] = []
        for attribute in attributes:
            if node_schema.check_if_attr_supports_profiles(attribute_schema=attribute):
                profile_attributes.append(attribute)
            if attribute.support_templates:
                template_attributes.append(attribute)

        scopes = [(node_schema.kind, attributes)]
        if profile_attributes:
            scopes.append((f"Profile{node_schema.kind}", profile_attributes))
        if template_attributes:
            scopes.append((f"Template{node_schema.kind}", template_attributes))
        return scopes

    def _repair_node_kinds(self, node_schema: NodeSchema, attribute: AttributeSchema) -> list[str]:
        """Return the instance kinds whose damaged nodes may receive the attribute's row."""
        node_kinds = [node_schema.kind]
        if node_schema.check_if_attr_supports_profiles(attribute_schema=attribute):
            node_kinds.append(f"Profile{node_schema.kind}")
        if attribute.support_templates:
            node_kinds.append(f"Template{node_schema.kind}")
        return node_kinds

    async def _detect_kind_damage(
        self, branch: Branch, node_schema: NodeSchema, attributes: list[AttributeSchema]
    ) -> dict[str, set[str]]:
        """Return the kind's damaged node uuids per attribute name."""
        damaged_uuids_by_attribute: dict[str, set[str]] = defaultdict(set)
        for instance_kind, instance_attributes in self._audit_scopes(node_schema=node_schema, attributes=attributes):
            query = await AttributeHealDetectionQuery.init(
                db=self.db,
                branch=branch,
                node_kinds=[instance_kind],
                attribute_names=[attribute.name for attribute in instance_attributes],
            )
            await query.execute(db=self.db)
            for pair in query.get_data():
                damaged_uuids_by_attribute[pair.attribute_name].add(pair.node_uuid)
        return dict(damaged_uuids_by_attribute)

    async def _repair_kind(
        self,
        branch: Branch,
        node_schema: NodeSchema,
        attributes: list[AttributeSchema],
        damaged_uuids_by_attribute: dict[str, set[str]],
        at: Timestamp,
        user_id: str,
    ) -> MigrationResult:
        result = MigrationResult()

        for attribute in attributes:
            repairer = next(repairer for repairer in self.repairers if repairer.supports(attribute))
            try:
                result.nbr_migrations_executed += await repairer.repair(
                    rows=MissingRows(
                        branch=branch,
                        node_schema=node_schema,
                        attribute=attribute,
                        node_kinds=self._repair_node_kinds(node_schema=node_schema, attribute=attribute),
                        node_uuids=damaged_uuids_by_attribute[attribute.name],
                        at=at,
                        user_id=user_id,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - one attribute's failure is reported, so it does not hide the others
                result.errors.append(f"{node_schema.kind}.{attribute.name} on branch {branch.name}: {exc}")
                break

        return result
