from __future__ import annotations

from collections import defaultdict
from itertools import batched
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.load_schema_branch import get_or_load_schema_branch
from infrahub.core.migrations.query.attribute_add import AttributeAddQuery
from infrahub.core.migrations.shared import (
    MigrationInput,
    MigrationRequiringRebase,
    MigrationResult,
    get_migration_console,
)
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import NodeSchema, SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.lock import initialize_lock
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter

from .queries import AttributeHealDetectionQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

NUMBER_POOL_ATTRIBUTE_KIND = "NumberPool"


class Migration076(MigrationRequiringRebase):
    """Backfill missing generic-inherited attribute rows on active nodes.

    In earlier versions, adding a generic to an existing kind did not create rows
    for the newly inherited attributes on the kind's pre-existing nodes, leaving
    active nodes without rows their schema requires. The audit covers exactly the
    attributes a kind inherits from its generics — the only rows this damage
    shape can affect — using each branch's processed schema, so an attribute
    defined by several generics is healed with the same effective definition the
    runtime write path uses. Profile and template instances of each kind are
    audited and repaired alongside concrete instances, restricted to the
    attributes they support.

    Every damaged (active node, inherited attribute) pair gets an active row
    created at migration run time: default-backed attributes carry the schema
    default (a null value when the attribute has none), pool-backed attributes a
    fresh reservation-aware allocation from the attribute's number pool, which is
    upserted when missing. The default branch is repaired at upgrade; every other
    branch is repaired by its post-upgrade rebase, after which it also sees the
    default branch's rows.

    The migration is idempotent and performs zero writes on healthy data.
    Validation re-runs the damage detection on the default branch and reports
    per-kind errors for any remaining damaged pair, which fails the upgrade; the
    per-branch pass re-validates its own scope before returning.
    """

    name: str = "076_heal_missing_attribute_rows"
    description: str = (
        "Backfill attribute rows that earlier versions failed to create when an "
        "existing kind started inheriting attributes from a generic"
    )
    minimum_version: int = 75
    repair_batch_size: int = 1000

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        result = MigrationResult()

        try:
            await self._ensure_runtime_context(db=migration_input.db)
            default_branch = await registry.get_branch(db=migration_input.db, branch=registry.default_branch)
            result = await self._heal_branch(migration_input=migration_input, branch=default_branch)
        except Exception as exc:  # noqa: BLE001 - a repair failure is reported, never raised out of a migration
            migration_input.console.print_exception()
            result.errors.append(f"{type(exc).__name__}: {exc}")

        return result

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        """Heal the branch's damage, assuming the branch was rebased first.

        The audit is restricted to kinds whose inherited attributes go beyond the
        default branch's schema: missing rows on a branch can only stem from
        inheritance the branch's own schema added, and post-rebase everything else
        is already covered by the default branch's rows. The branch is re-audited
        before returning, because the upgrade-time validation only covers the
        default branch.
        """
        db = migration_input.db
        result = MigrationResult()

        try:
            await self._ensure_runtime_context(db=db)
            if branch.name not in registry.branch:
                registry.branch[branch.name] = branch
            default_branch = await registry.get_branch(db=db, branch=registry.default_branch)
            baseline_schema = await get_or_load_schema_branch(db=db, branch=default_branch)
            result = await self._heal_branch(
                migration_input=migration_input, branch=branch, baseline_schema=baseline_schema
            )
            if result.errors:
                return result
            result.errors.extend(
                await self._detect_remaining_damage(db=db, branch=branch, baseline_schema=baseline_schema)
            )
        except Exception as exc:  # noqa: BLE001 - a repair failure is reported, never raised out of a migration
            migration_input.console.print_exception()
            result.errors.append(f"{type(exc).__name__}: {exc}")

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        """Audit the default branch; run after execute() at upgrade and after every per-branch pass."""
        result = MigrationResult()
        console = get_migration_console()

        try:
            await self._ensure_runtime_context(db=db)
            default_branch = await registry.get_branch(db=db, branch=registry.default_branch)
            result.errors.extend(await self._detect_remaining_damage(db=db, branch=default_branch))
        except Exception as exc:  # noqa: BLE001 - a repair failure is reported, never raised out of a migration
            console.print_exception()
            result.errors.append(f"{type(exc).__name__}: {exc}")

        return result

    async def _ensure_runtime_context(self, db: InfrahubDatabase) -> None:
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

    async def _heal_branch(
        self, migration_input: MigrationInput, branch: Branch, baseline_schema: SchemaBranch | None = None
    ) -> MigrationResult:
        """Detect and repair every damaged (node, inherited attribute) pair of the branch."""
        result = MigrationResult()
        db = migration_input.db
        console = migration_input.console

        audited_schemas = await self._audited_node_schemas(db=db, branch=branch, baseline_schema=baseline_schema)
        console.log(f"  Branch {branch.name}: auditing {len(audited_schemas)} kind(s) with inherited attributes")

        repaired_kinds = 0
        for index, node_schema in enumerate(audited_schemas, start=1):
            inherited_attributes = self._inherited_attributes(node_schema=node_schema)
            damaged_uuids_by_attribute = await self._detect_kind_damage(
                db=db, branch=branch, node_schema=node_schema, attributes=inherited_attributes
            )
            if not damaged_uuids_by_attribute:
                continue

            pair_count = sum(len(uuids) for uuids in damaged_uuids_by_attribute.values())
            node_count = len({uuid for uuids in damaged_uuids_by_attribute.values() for uuid in uuids})
            console.log(
                f"  ({index}/{len(audited_schemas)}) {node_schema.kind}: {pair_count} missing attribute "
                f"row(s) across {node_count} node(s); repairing"
            )

            kind_result = await self._repair_kind(
                migration_input=migration_input,
                branch=branch,
                node_schema=node_schema,
                attributes=[
                    attribute for attribute in inherited_attributes if attribute.name in damaged_uuids_by_attribute
                ],
                damaged_uuids_by_attribute=damaged_uuids_by_attribute,
            )
            result.errors.extend(kind_result.errors)
            result.nbr_migrations_executed += kind_result.nbr_migrations_executed
            repaired_kinds += 1
            if result.errors:
                break

        if repaired_kinds:
            console.log(
                f"  Branch {branch.name}: repaired {result.nbr_migrations_executed} attribute row(s) "
                f"across {repaired_kinds} kind(s)"
            )
        else:
            console.log(f"  No missing attribute rows detected on branch {branch.name}; nothing to repair.")

        return result

    async def _audited_node_schemas(
        self, db: InfrahubDatabase, branch: Branch, baseline_schema: SchemaBranch | None = None
    ) -> list[NodeSchema]:
        """Return the branch's node schemas that inherit at least one generic attribute.

        With a baseline, only kinds whose inherited attributes go beyond the
        baseline's schema are returned.
        """
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)
        audited: list[NodeSchema] = []
        for name in sorted(schema_branch.node_names):
            node_schema = schema_branch.get(name=name, duplicate=False)
            if not isinstance(node_schema, NodeSchema) or not self._inherited_attributes(node_schema=node_schema):
                continue
            if baseline_schema is not None and not self._inherits_beyond_baseline(
                node_schema=node_schema, baseline_schema=baseline_schema
            ):
                continue
            audited.append(node_schema)
        return audited

    @staticmethod
    def _inherits_beyond_baseline(node_schema: NodeSchema, baseline_schema: SchemaBranch) -> bool:
        """Return whether the kind inherits an attribute the baseline's schema does not define.

        Rows exist for every attribute the baseline defined — the runtime write path
        and the baseline's own heal guarantee it — so only attributes beyond the
        baseline can be missing. That covers nodes created on the branch too: a
        branch forked after the baseline gained the inheritance creates nodes from a
        schema that already carries it, so every row is written at creation; a branch
        forked before adopts the inheritance at rebase, where schema migrations create
        the rows for the branch's own nodes.
        """
        if node_schema.kind not in baseline_schema.node_names:
            return True
        baseline_node = baseline_schema.get(name=node_schema.kind, duplicate=False)
        inherited_names = {attribute.name for attribute in node_schema.attributes if attribute.inherited}
        return not inherited_names <= set(baseline_node.attribute_names)

    @staticmethod
    def _inherited_attributes(node_schema: NodeSchema) -> list[AttributeSchema]:
        return sorted(
            (attribute for attribute in node_schema.attributes if attribute.inherited),
            key=lambda attribute: attribute.name,
        )

    @staticmethod
    def _audit_scopes(
        node_schema: NodeSchema, attributes: list[AttributeSchema]
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

    @staticmethod
    def _repair_node_kinds(node_schema: NodeSchema, attribute: AttributeSchema) -> list[str]:
        """Return the instance kinds whose damaged nodes may receive the attribute's row.

        Profile and template instances are included only when the attribute passes
        the same support predicates that gate row creation on them.
        """
        node_kinds = [node_schema.kind]
        if node_schema.check_if_attr_supports_profiles(attribute_schema=attribute):
            node_kinds.append(f"Profile{node_schema.kind}")
        if attribute.support_templates:
            node_kinds.append(f"Template{node_schema.kind}")
        return node_kinds

    async def _detect_kind_damage(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        node_schema: NodeSchema,
        attributes: list[AttributeSchema],
    ) -> dict[str, set[str]]:
        """Return the kind's damaged node uuids per attribute name."""
        damaged_uuids_by_attribute: dict[str, set[str]] = defaultdict(set)
        for instance_kind, instance_attributes in self._audit_scopes(node_schema=node_schema, attributes=attributes):
            query = await AttributeHealDetectionQuery.init(
                db=db,
                branch=branch,
                node_kinds=[instance_kind],
                attribute_names=[attribute.name for attribute in instance_attributes],
            )
            await query.execute(db=db)
            for pair in query.get_data():
                damaged_uuids_by_attribute[pair.attribute_name].add(pair.node_uuid)
        return dict(damaged_uuids_by_attribute)

    async def _repair_kind(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        node_schema: NodeSchema,
        attributes: list[AttributeSchema],
        damaged_uuids_by_attribute: dict[str, set[str]],
    ) -> MigrationResult:
        result = MigrationResult()

        for attribute in attributes:
            try:
                if attribute.kind == NUMBER_POOL_ATTRIBUTE_KIND:
                    created = await self._repair_pool_backed_attribute(
                        migration_input=migration_input,
                        branch=branch,
                        node_schema=node_schema,
                        attribute=attribute,
                        node_uuids=damaged_uuids_by_attribute[attribute.name],
                    )
                else:
                    created = await self._repair_default_backed_attribute(
                        migration_input=migration_input,
                        branch=branch,
                        node_schema=node_schema,
                        attribute=attribute,
                        node_uuids=damaged_uuids_by_attribute[attribute.name],
                    )
                result.nbr_migrations_executed += created
            except Exception as exc:  # noqa: BLE001 - see the comment above: one attribute must not hide the others
                result.errors.append(f"{node_schema.kind}.{attribute.name} on branch {branch.name}: {exc}")
                break

        return result

    async def _repair_default_backed_attribute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        node_schema: NodeSchema,
        attribute: AttributeSchema,
        node_uuids: set[str],
    ) -> int:
        """Create the missing rows carrying the schema default; return the number created.

        Writes are chunked so a large repair neither exceeds the database's
        transaction memory limits nor runs silently; each chunk is one atomic
        auto-committed statement, and a rerun after a partial failure converges
        through the query's idempotency.
        """
        console = migration_input.console
        # sorted for deterministic chunk composition and reproducible logs
        multiple_batches = len(node_uuids) > self.repair_batch_size
        created = 0
        for uuid_batch in batched(sorted(node_uuids), self.repair_batch_size):
            query = await AttributeAddQuery.init(
                db=migration_input.db,
                branch=branch,
                at=migration_input.at,
                user_id=migration_input.user_id,
                node_kinds=self._repair_node_kinds(node_schema=node_schema, attribute=attribute),
                attribute_name=attribute.name,
                attribute_kind=attribute.kind,
                branch_support=attribute.get_branch().value,
                default_value=attribute.default_value,
                uuids=list(uuid_batch),
            )
            await query.execute(db=migration_input.db)
            created += query.num_of_results
            if multiple_batches:
                console.log(f"    {node_schema.kind}.{attribute.name}: created {created}/{len(node_uuids)} row(s)")

        console.log(f"    {node_schema.kind}.{attribute.name}: created {created} row(s)")
        return created

    async def _repair_pool_backed_attribute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        node_schema: NodeSchema,
        attribute: AttributeSchema,
        node_uuids: set[str],
    ) -> int:
        """Create the missing rows with per-node allocated values; return the number repaired.

        The pool is upserted the same way the schema change that introduces the
        attribute provisions it, so a damaged install missing the pool is healed
        rather than failed. Work is chunked: within a chunk, allocation and row
        write are interleaved per node inside one transaction, so every
        allocation sees the reservations of the previous ones; committed chunks
        survive a later failure, and allocations are reservation-aware, so
        healthy nodes and reruns never re-allocate. Pool exhaustion aborts the
        current chunk and surfaces as a per-attribute error.
        """
        db = migration_input.db
        console = migration_input.console

        upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
        number_pool = await upserter.upsert_number_pool(
            schema_node=node_schema,
            attribute=attribute,
            branch_name=branch.name,
            at=migration_input.at,
            user_id=migration_input.user_id,
        )

        # sorted for deterministic chunk composition, allocation order, and reproducible logs
        multiple_batches = len(node_uuids) > self.repair_batch_size
        repaired = 0
        for uuid_batch in batched(sorted(node_uuids), self.repair_batch_size):
            async with db.start_transaction() as dbt:
                query = await AttributeAddQuery.init(
                    db=dbt,
                    branch=branch,
                    at=migration_input.at,
                    user_id=migration_input.user_id,
                    node_kinds=self._repair_node_kinds(node_schema=node_schema, attribute=attribute),
                    attribute_name=attribute.name,
                    attribute_kind=attribute.kind,
                    branch_support=attribute.get_branch().value,
                    default_value=None,
                    uuids=list(uuid_batch),
                )
                await query.execute(db=dbt)

                # Counted per allocated node rather than from the rows the query created.
                nodes = await NodeManager.get_many(db=dbt, branch=branch, ids=list(uuid_batch))
                for node_uuid in sorted(nodes):
                    node = nodes[node_uuid]
                    number = await number_pool.get_resource(  # type: ignore[attr-defined]
                        db=dbt, branch=branch, identifier=node_uuid, attribute=attribute, at=migration_input.at
                    )
                    node_attribute = node.get_attribute(name=attribute.name)
                    node_attribute.value = number
                    node_attribute.set_source(number_pool.get_id())
                    await node.save(db=dbt, fields=[attribute.name], at=migration_input.at)
                    repaired += 1
            if multiple_batches:
                console.log(
                    f"    {node_schema.kind}.{attribute.name}: allocated {repaired}/{len(node_uuids)} pool value(s)"
                )

        console.log(f"    {node_schema.kind}.{attribute.name}: allocated {repaired} pool value(s)")
        return repaired

    async def _detect_remaining_damage(
        self, db: InfrahubDatabase, branch: Branch, baseline_schema: SchemaBranch | None = None
    ) -> list[str]:
        """Return one error per kind still carrying damaged pairs on the branch."""
        errors: list[str] = []
        for node_schema in await self._audited_node_schemas(db=db, branch=branch, baseline_schema=baseline_schema):
            damaged_uuids_by_attribute = await self._detect_kind_damage(
                db=db,
                branch=branch,
                node_schema=node_schema,
                attributes=self._inherited_attributes(node_schema=node_schema),
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
