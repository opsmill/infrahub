import re

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
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


@pytest.fixture
async def kind_override_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_kind_override_schema: SchemaBranch,
    ip_dataset_prefix_v4: dict,
) -> CoreIPAddressPool:
    """An address pool whose default kind is IpamIPAddress, with TestIPAddress as a sibling."""
    address_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db)
    await pool.new(
        db=db,
        name="pool1",
        resources=[ip_dataset_prefix_v4["net145"]],
        ip_namespace=ip_dataset_prefix_v4["ns1"],
        default_address_type="IpamIPAddress",
    )
    await pool.save(db=db)
    return pool


async def test_get_resource_address_type_overrides_pool_default(
    db: InfrahubDatabase, default_branch: Branch, kind_override_pool: CoreIPAddressPool
) -> None:
    """An explicit address_type wins over the pool's default_address_type."""
    node = await kind_override_pool.get_resource(
        db=db, branch=default_branch, address_type="TestIPAddress", peer_kind=InfrahubKind.IPADDRESS
    )

    assert node.get_kind() == "TestIPAddress"


async def test_get_resource_address_type_falls_back_to_pool_default(
    db: InfrahubDatabase, default_branch: Branch, kind_override_pool: CoreIPAddressPool
) -> None:
    """Without an override the pool default is used and is *not* re-validated."""
    node = await kind_override_pool.get_resource(db=db, branch=default_branch, peer_kind=InfrahubKind.IPADDRESS)

    assert node.get_kind() == "IpamIPAddress"


async def test_get_resource_address_type_not_allowed_for_peer_raises(
    db: InfrahubDatabase, default_branch: Branch, kind_override_pool: CoreIPAddressPool
) -> None:
    """A kind outside the peer generic's used_by is rejected."""
    with pytest.raises(ValidationError, match=re.escape("'TestMandatoryAddress' is not a valid kind")):
        await kind_override_pool.get_resource(
            db=db, branch=default_branch, address_type="TestMandatoryAddress", peer_kind=InfrahubKind.IPADDRESS
        )


async def test_get_resource_address_type_from_data_dict_is_validated(
    db: InfrahubDatabase, default_branch: Branch, kind_override_pool: CoreIPAddressPool
) -> None:
    """The untyped `data` dict is the second door into address_type and must be validated too."""
    with pytest.raises(ValidationError, match=re.escape("'TestMandatoryAddress' is not a valid kind")):
        await kind_override_pool.get_resource(
            db=db,
            branch=default_branch,
            data={"address_type": "TestMandatoryAddress"},
            peer_kind=InfrahubKind.IPADDRESS,
        )


async def test_get_resource_address_type_rejected_for_concrete_peer(
    db: InfrahubDatabase, default_branch: Branch, kind_override_pool: CoreIPAddressPool
) -> None:
    """A sibling kind is not allocatable when the relationship peer is a concrete kind.

    Both kinds carry an `address` attribute, so `node.new()` would happily build the wrong one.
    """
    with pytest.raises(ValidationError, match=re.escape("'TestIPAddress' is not a valid kind")):
        await kind_override_pool.get_resource(
            db=db, branch=default_branch, address_type="TestIPAddress", peer_kind="IpamIPAddress"
        )

    # The concrete peer's own kind stays allocatable.
    node = await kind_override_pool.get_resource(
        db=db, branch=default_branch, address_type="IpamIPAddress", peer_kind="IpamIPAddress"
    )
    assert node.get_kind() == "IpamIPAddress"


async def test_get_resource_without_peer_kind_is_unconstrained(
    db: InfrahubDatabase, default_branch: Branch, kind_override_pool: CoreIPAddressPool
) -> None:
    """Back-compat: callers that don't know the peer (node.new, migrations) stay unvalidated."""
    node = await kind_override_pool.get_resource(db=db, branch=default_branch, address_type="TestIPAddress")

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
    kind_override_pool: CoreIPAddressPool,
) -> None:
    """The counterpart of test_get_resource_conflicting_prefixlen_raises for the target kind.

    A reservation keeps the kind it was allocated with, so re-allocating the same identifier
    with a different explicit kind must error rather than silently return the original kind.
    """
    first = await kind_override_pool.get_resource(db=db, identifier="item1", branch=default_branch, prefixlen=30)
    assert first.get_kind() == "IpamIPAddress"

    expected_error = (
        f"IPAddressPool: pool1 | This resource is already allocated as "
        f"{first.get_attribute('address').value} of kind IpamIPAddress; its kind cannot be "
        "changed, only IpamIPAddress can be used."
    )
    with pytest.raises(ValidationError, match=rf"^{re.escape(expected_error)}$"):
        await kind_override_pool.get_resource(
            db=db, identifier="item1", branch=default_branch, address_type="TestIPAddress"
        )

    # The untyped `data` dict is the same door and must be guarded too.
    with pytest.raises(ValidationError, match=rf"^{re.escape(expected_error)}$"):
        await kind_override_pool.get_resource(
            db=db, identifier="item1", branch=default_branch, data={"address_type": "TestIPAddress"}
        )

    # The matching kind, or none at all, stays idempotent.
    same = await kind_override_pool.get_resource(
        db=db, identifier="item1", branch=default_branch, address_type="IpamIPAddress"
    )
    assert same.id == first.id

    same_no_kind = await kind_override_pool.get_resource(db=db, identifier="item1", branch=default_branch)
    assert same_no_kind.id == first.id


async def test_get_resource_reserved_kind_validated_against_peer(
    db: InfrahubDatabase,
    default_branch: Branch,
    kind_override_pool: CoreIPAddressPool,
) -> None:
    """A reservation created under a permissive peer cannot be reused by a narrower one.

    validate_reserved_kind only compares requested-vs-reserved, so it passes whenever the
    caller asks for nothing. The reserved node's *own* kind must therefore be checked against
    this caller's peer as well: `Relationship.set_peer` performs no kind check, so otherwise a
    TestIPAddress reserved through the broad BuiltinIPAddress generic would be attached to a
    relationship peering at TestNarrowAddress, which cannot hold it.
    """
    first = await kind_override_pool.get_resource(
        db=db,
        identifier="item1",
        branch=default_branch,
        address_type="TestIPAddress",
        peer_kind=InfrahubKind.IPADDRESS,
    )
    assert first.get_kind() == "TestIPAddress"

    with pytest.raises(
        ValidationError,
        match=re.escape("'TestIPAddress' is not a valid kind to allocate for 'TestNarrowAddress'"),
    ):
        await kind_override_pool.get_resource(
            db=db, identifier="item1", branch=default_branch, peer_kind="TestNarrowAddress"
        )

    # A peer that permits the reserved kind, a concrete peer of exactly that kind, or no peer
    # at all, all still get the reservation back.
    same = await kind_override_pool.get_resource(
        db=db, identifier="item1", branch=default_branch, peer_kind=InfrahubKind.IPADDRESS
    )
    assert same.id == first.id

    same_concrete_peer = await kind_override_pool.get_resource(
        db=db, identifier="item1", branch=default_branch, peer_kind="TestIPAddress"
    )
    assert same_concrete_peer.id == first.id

    same_no_peer = await kind_override_pool.get_resource(db=db, identifier="item1", branch=default_branch)
    assert same_no_peer.id == first.id
