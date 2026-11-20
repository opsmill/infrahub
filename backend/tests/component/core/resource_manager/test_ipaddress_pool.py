import re
from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PoolExhaustedError, ValidationError


async def test_get_next(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4: dict,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net145 = ip_dataset_prefix_v4["net145"]

    adress_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=adress_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net145], ip_namespace=ns1, default_address_type="IpamIPAddress")
    await pool.save(db=db)

    assert pool

    next_address = await pool.get_next(db=db, prefixlen=30)
    assert str(next_address) == "10.10.3.2/30"

    next_prefix = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id


@dataclass
class UnreadableReservationCase:
    name: str
    delete_first_branch: bool


UNREADABLE_RESERVATION_CASES: list[UnreadableReservationCase] = [
    UnreadableReservationCase(name="first-reservation-on-sibling-branch", delete_first_branch=False),
    UnreadableReservationCase(name="first-reservation-on-deleted-branch", delete_first_branch=True),
]


class TestGetResourceWithUnreadableReservation:
    @pytest.fixture(scope="class")
    async def namespace(
        self,
        db: InfrahubDatabase,
        register_core_models_schema_scope_class: SchemaBranch,
        register_ipam_schema_scope_class: SchemaBranch,
        default_ipnamespace_scope_class: Node | None,
    ) -> Node:
        namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await namespace.new(db=db, name="ns1")
        await namespace.save(db=db)
        return namespace

    @pytest.fixture(scope="class")
    async def pool_prefix(self, db: InfrahubDatabase, namespace: Node) -> Node:
        prefix = await Node.init(db=db, schema="IpamIPPrefix")
        await prefix.new(db=db, prefix="10.10.3.0/27", ip_namespace=namespace)
        await prefix.save(db=db)
        return prefix

    @pytest.mark.parametrize("case", UNREADABLE_RESERVATION_CASES, ids=lambda case: case.name)
    async def test_branch_keeps_its_own_address(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        namespace: Node,
        pool_prefix: Node,
        case: UnreadableReservationCase,
    ) -> None:
        """A branch that cannot read an identifier's first reservation keeps returning its own address."""
        address_pool_schema = registry.schema.get_node_schema(
            name=InfrahubKind.IPADDRESSPOOL, branch=default_branch_scope_class
        )
        pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db)
        await pool.new(
            db=db,
            name=f"pool-{case.name}",
            resources=[pool_prefix],
            ip_namespace=namespace,
            default_address_type="IpamIPAddress",
        )
        await pool.save(db=db)

        branch_a = await create_branch(branch_name=f"{case.name}-a", db=db)
        branch_b = await create_branch(branch_name=f"{case.name}-b", db=db)

        async def reserve(branch: Branch) -> Node:
            return await pool.get_resource(db=db, address_type="IpamIPAddress", identifier=case.name, branch=branch)

        address_a = await reserve(branch=branch_a)
        if case.delete_first_branch:
            await BranchDataDeleter(db=db, batch_size=5).delete(branch=branch_a)

        first = await reserve(branch=branch_b)
        second = await reserve(branch=branch_b)
        third = await reserve(branch=branch_b)

        assert first.id != address_a.id
        assert [second.id, third.id] == [first.id, first.id]


async def test_get_next_weighted(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4: dict,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net144 = ip_dataset_prefix_v4["net144"]
    net145 = ip_dataset_prefix_v4["net145"]

    net144.allocation_weight.value = 100
    await net144.save(db=db)
    net145.allocation_weight.value = 200
    await net145.save(db=db)

    adress_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=adress_pool_schema, db=db)
    await pool.new(
        db=db, name="pool1", resources=[net144, net145], ip_namespace=ns1, default_address_type="IpamIPAddress"
    )
    await pool.save(db=db)

    assert pool

    next_address = await pool.get_next(db=db, prefixlen=30)
    assert str(next_address) == "10.10.3.2/30"

    next_prefix = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id


async def test_get_resource_conflicting_prefixlen_raises(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4: dict,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net145 = ip_dataset_prefix_v4["net145"]

    adress_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=adress_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net145], ip_namespace=ns1, default_address_type="IpamIPAddress")
    await pool.save(db=db)

    first = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch, prefixlen=30
    )

    # An explicit prefixlen that conflicts with the existing reservation is rejected
    # rather than silently ignored.
    expected_error = (
        f"IPAddressPool: pool1 | This resource is already allocated as {first.get_attribute('address').value}; "
        "its prefix length cannot be changed, only /30 can be used."
    )
    with pytest.raises(ValidationError, match=rf"^{re.escape(expected_error)}$"):
        await pool.get_resource(
            db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch, prefixlen=28
        )

    # The same prefixlen, or none at all, stays idempotent.
    same = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch, prefixlen=30
    )
    assert same.id == first.id

    same_no_prefixlen = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch
    )
    assert same_no_prefixlen.id == first.id


async def test_get_resource_address_type_overrides_pool_default(
    db: InfrahubDatabase, default_branch: Branch, kind_override_address_pool: CoreIPAddressPool
) -> None:
    """An explicit address_type wins over the pool's default_address_type."""
    node = await kind_override_address_pool.get_resource(
        db=db, branch=default_branch, address_type="TestIPAddress", peer_kind=InfrahubKind.IPADDRESS
    )

    assert node.get_kind() == "TestIPAddress"


async def test_get_resource_data_cannot_set_the_id_of_the_address_without_a_check(
    db: InfrahubDatabase, default_branch: Branch, kind_override_address_pool: CoreIPAddressPool
) -> None:
    """Only `id` in the data names the uuid of the new address, and that one is checked against the database."""
    node = await kind_override_address_pool.get_resource(
        db=db,
        branch=default_branch,
        peer_kind=InfrahubKind.IPADDRESS,
        data={"generated_id": kind_override_address_pool.id},
    )

    assert node.id != kind_override_address_pool.id


async def test_get_resource_address_type_falls_back_to_pool_default(
    db: InfrahubDatabase, default_branch: Branch, kind_override_address_pool: CoreIPAddressPool
) -> None:
    """Without an explicit kind the pool's default kind is allocated."""
    node = await kind_override_address_pool.get_resource(db=db, branch=default_branch, peer_kind=InfrahubKind.IPADDRESS)

    assert node.get_kind() == "IpamIPAddress"


async def test_get_resource_address_type_not_allowed_for_peer_raises(
    db: InfrahubDatabase, default_branch: Branch, kind_override_address_pool: CoreIPAddressPool
) -> None:
    """A kind outside the peer generic's used_by is rejected."""
    with pytest.raises(ValidationError, match=re.escape("'TestMandatoryAddress' is not a valid kind")):
        await kind_override_address_pool.get_resource(
            db=db, branch=default_branch, address_type="TestMandatoryAddress", peer_kind=InfrahubKind.IPADDRESS
        )


async def test_get_resource_address_type_from_data_dict_is_validated(
    db: InfrahubDatabase, default_branch: Branch, kind_override_address_pool: CoreIPAddressPool
) -> None:
    """The untyped `data` dict is the second door into address_type and must be validated too."""
    with pytest.raises(ValidationError, match=re.escape("'TestMandatoryAddress' is not a valid kind")):
        await kind_override_address_pool.get_resource(
            db=db,
            branch=default_branch,
            data={"address_type": "TestMandatoryAddress"},
            peer_kind=InfrahubKind.IPADDRESS,
        )


async def test_get_resource_address_type_rejected_for_concrete_peer(
    db: InfrahubDatabase, default_branch: Branch, kind_override_address_pool: CoreIPAddressPool
) -> None:
    """A sibling kind is not allocatable when the relationship peer is a concrete kind."""
    with pytest.raises(ValidationError, match=re.escape("'TestIPAddress' is not a valid kind")):
        await kind_override_address_pool.get_resource(
            db=db, branch=default_branch, address_type="TestIPAddress", peer_kind="IpamIPAddress"
        )

    node = await kind_override_address_pool.get_resource(
        db=db, branch=default_branch, address_type="IpamIPAddress", peer_kind="IpamIPAddress"
    )
    assert node.get_kind() == "IpamIPAddress"


async def test_get_resource_without_peer_kind_is_unconstrained(
    db: InfrahubDatabase, default_branch: Branch, kind_override_address_pool: CoreIPAddressPool
) -> None:
    """With no peer kind given, the requested address_type is allocated without validation."""
    node = await kind_override_address_pool.get_resource(db=db, branch=default_branch, address_type="TestIPAddress")

    assert node.get_kind() == "TestIPAddress"


async def test_get_next_full(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4: dict,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net147 = ip_dataset_prefix_v4["net147"]

    adress_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=adress_pool_schema, db=db)
    await pool.new(db=db, name="pool2", resources=[net147], ip_namespace=ns1, default_address_type="IpamIPAddress")
    await pool.save(db=db)

    assert pool

    with pytest.raises(PoolExhaustedError, match="There are no more addresses available in this pool"):
        await pool.get_next(db=db, prefixlen=30)


async def test_get_resource_conflicting_address_type_raises(
    db: InfrahubDatabase,
    default_branch: Branch,
    kind_override_address_pool: CoreIPAddressPool,
) -> None:
    """A reservation keeps the kind it was allocated with.

    Re-allocating the same identifier with a different explicit kind errors; with the same kind,
    or none at all, it returns the original resource.
    """
    first = await kind_override_address_pool.get_resource(
        db=db, identifier="item1", branch=default_branch, prefixlen=30
    )
    assert first.get_kind() == "IpamIPAddress"

    expected_error = (
        f"IPAddressPool: pool1 | This resource is already allocated as "
        f"{first.get_attribute('address').value} of kind IpamIPAddress; its kind cannot be "
        "changed, only IpamIPAddress can be used."
    )
    with pytest.raises(ValidationError, match=rf"^{re.escape(expected_error)}$"):
        await kind_override_address_pool.get_resource(
            db=db, identifier="item1", branch=default_branch, address_type="TestIPAddress"
        )

    with pytest.raises(ValidationError, match=rf"^{re.escape(expected_error)}$"):
        await kind_override_address_pool.get_resource(
            db=db, identifier="item1", branch=default_branch, data={"address_type": "TestIPAddress"}
        )

    same = await kind_override_address_pool.get_resource(
        db=db, identifier="item1", branch=default_branch, address_type="IpamIPAddress"
    )
    assert same.id == first.id

    same_no_kind = await kind_override_address_pool.get_resource(db=db, identifier="item1", branch=default_branch)
    assert same_no_kind.id == first.id
