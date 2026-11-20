from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.uuidt import UUIDT

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.node import NodeCheckIDQuery
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from tests.adapters.lock.timeline import LockAction
from tests.helpers.agnostic_edges import IsReservedEdge, is_reserved_edge_on
from tests.helpers.constants import LOCK_WAIT_TIMEOUT_SECONDS
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.db_transaction_tracker import TransactionTrackingInfrahubDatabase
from tests.helpers.ip_pool import create_namespace, create_prefix
from tests.helpers.lock import wait_until_waiting
from tests.helpers.number_pool import (
    SCOPED_CARD,
    SCOPED_CHASSIS,
    SCOPED_SITE,
    add_pool_range,
    pool_lock_events,
    provision_schema_number_pools,
    save_schema_kinds,
    scoped_site,
    stored_scope,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.lock import RecordingLockRegistry

MODULE_KIND = "ScopeModule"
ADDRESS_KIND = "IpamIPAddress"
PREFIX_KIND = "IpamIPPrefix"
CHASSIS_SCOPED_POOL = "card-scoped-by-chassis"


class Level(StrEnum):
    OBJECT = "object"
    COMPONENT = "component"
    NESTED_COMPONENT = "nested-component"


LEVEL_KINDS = {
    Level.OBJECT: SCOPED_CHASSIS.kind,
    Level.COMPONENT: SCOPED_CARD.kind,
    Level.NESTED_COMPONENT: MODULE_KIND,
}


class PoolSource(StrEnum):
    TEMPLATE = "template"
    """The template of the level names the pool with a `_from_resource_pool` relationship."""
    SCHEMA = "schema"
    """The schema declares the pool with a NumberPool attribute."""


class PoolType(StrEnum):
    NUMBER = "number"
    SCOPED_NUMBER = "scoped-number"
    ADDRESS = "address"
    PREFIX = "prefix"


POOLED_FIELDS = {
    (PoolSource.TEMPLATE, PoolType.NUMBER): "vlan_id",
    (PoolSource.TEMPLATE, PoolType.SCOPED_NUMBER): "vlan_id",
    (PoolSource.SCHEMA, PoolType.NUMBER): "serial",
    (PoolSource.SCHEMA, PoolType.SCOPED_NUMBER): "site_serial",
    (PoolSource.TEMPLATE, PoolType.ADDRESS): "address",
    (PoolSource.TEMPLATE, PoolType.PREFIX): "prefix",
}

EXPECTED_IP_VALUES = {
    (Level.OBJECT, PoolType.ADDRESS): "10.1.0.1/24",
    (Level.COMPONENT, PoolType.ADDRESS): "10.2.0.1/24",
    (Level.OBJECT, PoolType.PREFIX): "10.3.0.0/28",
    (Level.COMPONENT, PoolType.PREFIX): "10.4.0.0/28",
}
IP_POOL_RESOURCES = {
    (Level.OBJECT, PoolType.ADDRESS): "10.1.0.0/24",
    (Level.COMPONENT, PoolType.ADDRESS): "10.2.0.0/24",
    (Level.OBJECT, PoolType.PREFIX): "10.3.0.0/24",
    (Level.COMPONENT, PoolType.PREFIX): "10.4.0.0/24",
}


@dataclass(frozen=True)
class PoolLockCase:
    """A pool drawn from by the object created from a template, or by one of its components."""

    level: Level
    source: PoolSource
    pool_type: PoolType

    @property
    def name(self) -> str:
        return f"{self.level}-{self.source}-{self.pool_type}"

    @property
    def field(self) -> str:
        return POOLED_FIELDS[self.source, self.pool_type]


POOL_LOCK_CASES = [
    PoolLockCase(level=level, source=source, pool_type=pool_type)
    for level in (Level.OBJECT, Level.COMPONENT)
    for source, pool_type in POOLED_FIELDS
] + [PoolLockCase(level=Level.NESTED_COMPONENT, source=PoolSource.TEMPLATE, pool_type=PoolType.SCOPED_NUMBER)]


@dataclass
class PoolLockDataset:
    """A chassis holding cards holding modules, each in a site, and one pool for each case.

    Every kind has the fields of `POOLED_FIELDS` except the module, which has only `vlan_id`.
    """

    branch: Branch
    site: Node
    pools: dict[str, Node]


def _pooled_fields() -> tuple[list[AttributeSchema], list[RelationshipSchema]]:
    attributes = [
        AttributeSchema(
            name="serial",
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(start_range=1, end_range=100),
        ),
        AttributeSchema(
            name="site_serial",
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(start_range=1, end_range=100, allocation_scope=["site"]),
        ),
    ]
    relationships = [
        RelationshipSchema(
            name="address",
            peer=ADDRESS_KIND,
            kind=RelationshipKind.ATTRIBUTE,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
        RelationshipSchema(
            name="prefix",
            peer=PREFIX_KIND,
            kind=RelationshipKind.ATTRIBUTE,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
    ]
    return attributes, relationships


def _site_relationship(identifier: str) -> RelationshipSchema:
    return RelationshipSchema(
        name="site",
        peer=SCOPED_SITE.kind,
        identifier=identifier,
        kind=RelationshipKind.ATTRIBUTE,
        cardinality=RelationshipCardinality.ONE,
        optional=False,
    )


def pool_lock_schema() -> SchemaRoot:
    """The chassis and card kinds with every pooled field, a site on each, and a module held by the card."""
    chassis = deepcopy(SCOPED_CHASSIS)
    card = deepcopy(SCOPED_CARD)
    chassis.attributes.append(AttributeSchema(name="vlan_id", kind="Number", optional=True))
    for kind, site_identifier in ((chassis, "scope_chassis__site"), (card, "scope_card__site")):
        attributes, relationships = _pooled_fields()
        kind.attributes.extend(attributes)
        kind.relationships.extend([*relationships, _site_relationship(identifier=site_identifier)])
    card.relationships.append(
        RelationshipSchema(
            name="modules",
            peer=MODULE_KIND,
            identifier="scope_card__modules",
            kind=RelationshipKind.COMPONENT,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
        )
    )
    module = NodeSchema(
        name="Module",
        namespace="Scope",
        generate_template=True,
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(name="vlan_id", kind="Number", optional=True),
        ],
        relationships=[
            RelationshipSchema(
                name="card",
                peer=SCOPED_CARD.kind,
                identifier="scope_card__modules",
                kind=RelationshipKind.PARENT,
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
            _site_relationship(identifier="scope_module__site"),
        ],
    )
    return SchemaRoot(nodes=[deepcopy(SCOPED_SITE), chassis, card, module])


async def _number_pool(db: InfrahubDatabase, kind: str, scope: str | None) -> Node:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=f"{kind}-{scope or 'unscoped'}",
        node=kind,
        node_attribute="vlan_id",
        start_range=1,
        end_range=100,
        allocation_scope=stored_scope(names=[scope], kind=kind) if scope else None,
    )
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=100)
    return pool


async def _ip_pool(db: InfrahubDatabase, namespace: Node, name: str, pool_type: PoolType, resource: str) -> Node:
    prefix = await create_prefix(db=db, namespace=namespace, value=resource)
    pool: CoreIPAddressPool | CoreIPPrefixPool
    if pool_type is PoolType.ADDRESS:
        pool = await CoreIPAddressPool.init(db=db, schema=InfrahubKind.IPADDRESSPOOL)
        await pool.new(db=db, name=name, resources=[prefix], ip_namespace=namespace, default_address_type=ADDRESS_KIND)
    else:
        pool = await CoreIPPrefixPool.init(db=db, schema=InfrahubKind.IPPREFIXPOOL)
        await pool.new(
            db=db,
            name=name,
            resources=[prefix],
            ip_namespace=namespace,
            default_prefix_type=PREFIX_KIND,
            default_prefix_length=28,
        )
    await pool.save(db=db)
    return pool


async def _schema_pool(db: InfrahubDatabase, branch: Branch, kind: str, attribute_name: str) -> Node:
    parameters = registry.schema.get_node_schema(name=kind, branch=branch).get_attribute(name=attribute_name).parameters
    assert isinstance(parameters, NumberPoolParameters)
    assert parameters.number_pool_id is not None
    return await NodeManager.get_one(db=db, id=parameters.number_pool_id, branch=branch, raise_on_error=True)


async def _hold(name: str, held: asyncio.Event, release: asyncio.Event) -> None:
    async with lock.registry.get(name=name):
        held.set()
        await release.wait()


class TestPoolLocksOfACreateFromATemplate:
    """Each test creates a chassis from a template while another task holds the lock of one pool it draws from."""

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        register_ipam_schema_scope_class: SchemaBranch,
        init_nodes_registry_scope_class: None,
    ) -> PoolLockDataset:
        branch = default_branch_scope_class
        await save_schema_kinds(db=db, schema=pool_lock_schema())
        await provision_schema_number_pools(db=db)
        site = await scoped_site(db=db, branch=branch, name="site-a")
        namespace = await create_namespace(db=db)
        pools: dict[str, Node] = {}
        for case in POOL_LOCK_CASES:
            kind = LEVEL_KINDS[case.level]
            if case.source is PoolSource.SCHEMA:
                pools[case.name] = await _schema_pool(db=db, branch=branch, kind=kind, attribute_name=case.field)
            elif case.pool_type in {PoolType.NUMBER, PoolType.SCOPED_NUMBER}:
                pools[case.name] = await _number_pool(
                    db=db, kind=kind, scope="site" if case.pool_type is PoolType.SCOPED_NUMBER else None
                )
            else:
                pools[case.name] = await _ip_pool(
                    db=db,
                    namespace=namespace,
                    name=case.name,
                    pool_type=case.pool_type,
                    resource=IP_POOL_RESOURCES[case.level, case.pool_type],
                )
        pools[CHASSIS_SCOPED_POOL] = await _number_pool(db=db, kind=SCOPED_CARD.kind, scope="chassis")
        return PoolLockDataset(branch=branch, site=site, pools=pools)

    async def _template(self, db: InfrahubDatabase, dataset: PoolLockDataset, case: PoolLockCase) -> Node:
        """A chassis template with a card and a module below it, where the level of the case names its pool."""
        levels = [Level.OBJECT, Level.COMPONENT, Level.NESTED_COMPONENT]
        parent_fields = {Level.COMPONENT: "chassis", Level.NESTED_COMPONENT: "card"}
        templates: dict[Level, Node] = {}
        for index, level in enumerate(levels[: levels.index(case.level) + 1]):
            fields: dict[str, Any] = {"template_name": f"{level}-of-{case.name}", "site": dataset.site}
            if level is not Level.OBJECT:
                fields["name"] = f"{level}-of-{case.name}"
                fields[parent_fields[level]] = templates[levels[index - 1]].id
            if level is case.level and case.source is PoolSource.TEMPLATE:
                fields[f"{case.field}_from_resource_pool"] = {"id": dataset.pools[case.name].id}
            template = await Node.init(db=db, schema=f"Template{LEVEL_KINDS[level]}", branch=dataset.branch)
            await template.new(db=db, **fields)
            await template.save(db=db)
            templates[level] = template
        return templates[Level.OBJECT]

    def _lock_name(self, dataset: PoolLockDataset, case: PoolLockCase) -> str:
        pool_id = dataset.pools[case.name].id
        if case.pool_type is PoolType.NUMBER:
            return f"resource_pool.{pool_id}.all"
        if case.pool_type is PoolType.SCOPED_NUMBER:
            return f"resource_pool.{pool_id}.{dataset.site.id}"
        return f"resource_pool.{pool_id}"

    async def _created_at_level(
        self, db: InfrahubDatabase, dataset: PoolLockDataset, chassis: Node, level: Level
    ) -> Node:
        if level is Level.OBJECT:
            return chassis
        cards = await NodeManager.query(
            db=db, schema=SCOPED_CARD.kind, branch=dataset.branch, filters={"chassis__ids": [chassis.id]}
        )
        assert len(cards) == 1
        if level is Level.COMPONENT:
            return cards[0]
        modules = await NodeManager.query(
            db=db, schema=MODULE_KIND, branch=dataset.branch, filters={"card__ids": [cards[0].id]}
        )
        assert len(modules) == 1
        return modules[0]

    @pytest.mark.parametrize("case", POOL_LOCK_CASES, ids=[case.name for case in POOL_LOCK_CASES])
    async def test_the_create_waits_for_the_lock_of_the_pool_before_its_transaction(
        self,
        db: InfrahubDatabase,
        dataset: PoolLockDataset,
        recording_lock_registry: RecordingLockRegistry,
        case: PoolLockCase,
    ) -> None:
        template = await self._template(db=db, dataset=dataset, case=case)
        lock_name = self._lock_name(dataset=dataset, case=case)
        tracking_db = TransactionTrackingInfrahubDatabase.from_db(db=db)
        held = asyncio.Event()
        release = asyncio.Event()
        holder = asyncio.create_task(_hold(name=lock_name, held=held, release=release))
        await asyncio.wait_for(held.wait(), timeout=LOCK_WAIT_TIMEOUT_SECONDS)

        async with tracking_db.start_session() as session_db:
            write = asyncio.create_task(
                create_node(
                    data={"name": {"value": f"chassis-of-{case.name}"}, "object_template": {"id": template.id}},
                    db=session_db,
                    branch=dataset.branch,
                    schema=session_db.schema.get(name=SCOPED_CHASSIS.kind, branch=dataset.branch, duplicate=False),
                )
            )
            try:
                await wait_until_waiting(timeline=recording_lock_registry.timeline, name=lock_name)
                open_transactions_while_waiting = tracking_db.transaction_usage.open_transactions
            finally:
                release.set()
                await asyncio.wait_for(holder, timeout=LOCK_WAIT_TIMEOUT_SECONDS)
            chassis = await asyncio.wait_for(write, timeout=LOCK_WAIT_TIMEOUT_SECONDS)

        assert open_transactions_while_waiting == 0
        created = await self._created_at_level(db=db, dataset=dataset, chassis=chassis, level=case.level)
        if case.pool_type in {PoolType.ADDRESS, PoolType.PREFIX}:
            peer = await created.get_relationship(case.field).get_peer(db=db, raise_on_error=True)
            assert peer.get_attribute(case.field).value == EXPECTED_IP_VALUES[case.level, case.pool_type]
        else:
            assert (
                await is_reserved_edge_on(
                    db=db, pool_id=dataset.pools[case.name].id, node_id=created.id, attribute_name=case.field
                )
                == IsReservedEdge.OPEN
            )

    async def test_a_division_holding_an_object_whose_id_the_payload_sets_is_locked_before_the_transaction(
        self, db: InfrahubDatabase, dataset: PoolLockDataset, recording_lock_registry: RecordingLockRegistry
    ) -> None:
        """Another write can name the chassis by the id the payload sets, so the division of its card is contended."""
        pool = dataset.pools[CHASSIS_SCOPED_POOL]
        template = await Node.init(db=db, schema=f"Template{SCOPED_CHASSIS.kind}", branch=dataset.branch)
        await template.new(db=db, template_name="chassis-with-an-id", site=dataset.site)
        await template.save(db=db)
        subtemplate = await Node.init(db=db, schema=f"Template{SCOPED_CARD.kind}", branch=dataset.branch)
        await subtemplate.new(
            db=db,
            template_name="card-of-chassis-with-an-id",
            name="card-of-chassis-with-an-id",
            chassis=template.id,
            site=dataset.site,
            vlan_id_from_resource_pool={"id": pool.id},
        )
        await subtemplate.save(db=db)
        chassis_id = str(UUIDT())
        lock_name = f"resource_pool.{pool.id}.{chassis_id}"
        tracking_db = TransactionTrackingInfrahubDatabase.from_db(db=db)
        held = asyncio.Event()
        release = asyncio.Event()
        holder = asyncio.create_task(_hold(name=lock_name, held=held, release=release))
        await asyncio.wait_for(held.wait(), timeout=LOCK_WAIT_TIMEOUT_SECONDS)

        async with tracking_db.start_session() as session_db:
            write = asyncio.create_task(
                create_node(
                    data={
                        "id": chassis_id,
                        "name": {"value": "chassis-with-an-id"},
                        "object_template": {"id": template.id},
                    },
                    db=session_db,
                    branch=dataset.branch,
                    schema=session_db.schema.get(name=SCOPED_CHASSIS.kind, branch=dataset.branch, duplicate=False),
                )
            )
            try:
                await wait_until_waiting(timeline=recording_lock_registry.timeline, name=lock_name)
                open_transactions_while_waiting = tracking_db.transaction_usage.open_transactions
            finally:
                release.set()
                await asyncio.wait_for(holder, timeout=LOCK_WAIT_TIMEOUT_SECONDS)
            chassis = await asyncio.wait_for(write, timeout=LOCK_WAIT_TIMEOUT_SECONDS)

        assert open_transactions_while_waiting == 0
        assert chassis.id == chassis_id
        card = await self._created_at_level(db=db, dataset=dataset, chassis=chassis, level=Level.COMPONENT)
        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=card.id, attribute_name="vlan_id")
            == IsReservedEdge.OPEN
        )

    async def test_a_division_holding_the_object_created_is_locked_once_for_all_its_components(
        self, db: InfrahubDatabase, dataset: PoolLockDataset, recording_lock_registry: RecordingLockRegistry
    ) -> None:
        """Two cards draw in the division of their new chassis, whose lock the create takes once and keeps."""
        pool = dataset.pools[CHASSIS_SCOPED_POOL]
        template = await Node.init(db=db, schema=f"Template{SCOPED_CHASSIS.kind}", branch=dataset.branch)
        await template.new(db=db, template_name="chassis-with-two-cards", site=dataset.site)
        await template.save(db=db)
        for index in (1, 2):
            subtemplate = await Node.init(db=db, schema=f"Template{SCOPED_CARD.kind}", branch=dataset.branch)
            await subtemplate.new(
                db=db,
                template_name=f"card-{index}-of-chassis-with-two-cards",
                name=f"card-{index}",
                chassis=template.id,
                site=dataset.site,
                vlan_id_from_resource_pool={"id": pool.id},
            )
            await subtemplate.save(db=db)
        timeline = recording_lock_registry.timeline
        start = timeline.checkpoint("write")

        chassis = await create_node(
            data={"name": {"value": "chassis-with-two-cards"}, "object_template": {"id": template.id}},
            db=db,
            branch=dataset.branch,
            schema=db.schema.get(name=SCOPED_CHASSIS.kind, branch=dataset.branch, duplicate=False),
        )

        lock_name = f"resource_pool.{pool.id}.{chassis.id}"
        assert pool_lock_events(timeline=timeline, pool=pool, after=start) == [
            (lock_name, LockAction.ACQUIRE),
            (lock_name, LockAction.RELEASE),
        ]

    async def test_the_locks_of_a_create_name_the_object_created_without_checking_its_id(
        self, db: InfrahubDatabase, dataset: PoolLockDataset, recording_lock_registry: RecordingLockRegistry
    ) -> None:
        template = await Node.init(db=db, schema=f"Template{SCOPED_CHASSIS.kind}", branch=dataset.branch)
        await template.new(db=db, template_name="chassis-without-an-id", site=dataset.site)
        await template.save(db=db)
        counting_db = CountingInfrahubDatabase.from_db(db=db)

        async with counting_db.start_session() as session_db:
            chassis = await create_node(
                data={"name": {"value": "chassis-without-an-id"}, "object_template": {"id": template.id}},
                db=session_db,
                branch=dataset.branch,
                schema=session_db.schema.get(name=SCOPED_CHASSIS.kind, branch=dataset.branch, duplicate=False),
            )

        site_lock_prefix = "relationship_count.scope_chassis__site."
        assert recording_lock_registry.timeline.acquire_sequence(prefix=site_lock_prefix) == [
            f"{site_lock_prefix}{chassis.id}"
        ]
        assert counting_db.count_for(NodeCheckIDQuery.name) == 0
