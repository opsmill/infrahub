import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def ip_dataset_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    # -----------------------
    # Namespace NS1
    # -----------------------

    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    net161 = await Node.init(db=db, schema=prefix_schema)
    await net161.new(db=db, prefix="2001:db8::/48", ip_namespace=ns1)
    await net161.save(db=db)

    net162 = await Node.init(db=db, schema=prefix_schema)
    await net162.new(db=db, prefix="2001:db8::/64", ip_namespace=ns1, parent=net161)
    await net162.save(db=db)

    net146 = await Node.init(db=db, schema=prefix_schema)
    await net146.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns1)
    await net146.save(db=db)

    net140 = await Node.init(db=db, schema=prefix_schema)
    await net140.new(db=db, prefix="10.10.0.0/16", ip_namespace=ns1, parent=net146)
    await net140.save(db=db)

    net142 = await Node.init(db=db, schema=prefix_schema)
    await net142.new(db=db, prefix="10.10.1.0/24", parent=net140, ip_namespace=ns1)
    await net142.save(db=db)

    net143 = await Node.init(db=db, schema=prefix_schema)
    await net143.new(db=db, prefix="10.10.1.0/27", parent=net142, ip_namespace=ns1)
    await net143.save(db=db)

    net144 = await Node.init(db=db, schema=prefix_schema)
    await net144.new(db=db, prefix="10.10.2.0/24", parent=net140, ip_namespace=ns1)
    await net144.save(db=db)

    net145 = await Node.init(db=db, schema=prefix_schema)
    await net145.new(db=db, prefix="10.10.3.0/27", parent=net140, ip_namespace=ns1)
    await net145.save(db=db)

    address10 = await Node.init(db=db, schema=address_schema)
    await address10.new(db=db, address="10.10.0.0", ip_prefix=net140, ip_namespace=ns1)
    await address10.save(db=db)

    address11 = await Node.init(db=db, schema=address_schema)
    await address11.new(db=db, address="10.10.1.1", ip_prefix=net143, ip_namespace=ns1)
    await address11.save(db=db)

    # -----------------------
    # Namespace NS2
    # -----------------------
    ns2 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns2.new(db=db, name="ns2")
    await ns2.save(db=db)

    net240 = await Node.init(db=db, schema=prefix_schema)
    await net240.new(db=db, prefix="10.10.0.0/15", ip_namespace=ns2)
    await net240.save(db=db)

    net241 = await Node.init(db=db, schema=prefix_schema)
    await net241.new(db=db, prefix="10.10.0.0/24", parent=net240, ip_namespace=ns2)
    await net241.save(db=db)

    net242 = await Node.init(db=db, schema=prefix_schema)
    await net242.new(db=db, prefix="10.10.4.0/27", parent=net240, ip_namespace=ns2)
    await net242.save(db=db)

    data = {
        "ns1": ns1,
        "ns2": ns2,
        "net161": net161,
        "net162": net162,
        "net140": net140,
        "net142": net142,
        "net143": net143,
        "net144": net144,
        "net145": net145,
        "net146": net146,
        "address10": address10,
        "address11": address11,
        "net240": net240,
        "net241": net241,
        "net242": net242,
    }
    return data
