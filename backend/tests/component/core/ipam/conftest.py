from collections.abc import Generator
from pathlib import Path

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import (
    create_ipam_namespace,
)
from infrahub.core.node import Node
from infrahub.core.query.delete import DeleteAfterTimeQuery
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.conftest import (
    do_default_branch,
    do_empty_database,
    do_local_storage_dir,
    do_register_core_models_schema,
    do_register_internal_models_schema,
    do_reset_registry,
)


@pytest.fixture(scope="module")
async def register_internal_models_schema(default_branch: Branch) -> SchemaBranch:
    return await do_register_internal_models_schema(branch=default_branch)


@pytest.fixture(scope="module")
async def register_core_models_schema(default_branch: Branch, register_internal_models_schema) -> SchemaBranch:
    return await do_register_core_models_schema(branch=default_branch)


@pytest.fixture(scope="module")
def local_storage_dir(tmp_path_module_scope: Path) -> Path:
    return do_local_storage_dir(tmp_path=tmp_path_module_scope)


@pytest.fixture(scope="module")
async def empty_database(db: InfrahubDatabase) -> None:
    await do_empty_database(db=db)


@pytest.fixture(scope="module")
async def reset_registry(db: InfrahubDatabase) -> None:
    await do_reset_registry(db=db)


@pytest.fixture(scope="module")
async def default_branch(reset_registry, local_storage_dir, empty_database, db: InfrahubDatabase) -> Branch:
    return await do_default_branch(db=db)


@pytest.fixture(scope="module")
async def default_ipnamespace(db: InfrahubDatabase, register_core_models_schema) -> Node | None:
    if not registry._default_ipnamespace:
        ip_namespace = await create_ipam_namespace(db=db)
        registry.default_ipnamespace = ip_namespace.id
        return ip_namespace
    return None


@pytest.fixture(scope="module")
async def register_ipam_schema(default_branch: Branch, ipam_schema: SchemaRoot) -> SchemaBranch:
    schema_branch = registry.schema.register_schema(schema=ipam_schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    return schema_branch


@pytest.fixture(scope="module")
async def ip_dataset_01_load(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> dict[str, Node]:
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


@pytest.fixture(scope="module")
async def diff_repository(db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
    component_registry = get_component_registry()
    return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)


@pytest.fixture(scope="module")
def start_time() -> Timestamp:
    return Timestamp()


@pytest.fixture(scope="function")
async def ip_dataset_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    ip_dataset_01_load,
    diff_repository: DiffRepository,
    start_time: Timestamp,
) -> Generator[dict[str, Node], None, None]:
    yield ip_dataset_01_load

    all_diff_roots = await diff_repository.get_roots_metadata()
    root_uuids_to_delete = []
    for diff_root in all_diff_roots:
        if start_time <= diff_root.from_time:
            root_uuids_to_delete.append(diff_root.uuid)
    await diff_repository.delete_diff_roots(diff_root_uuids=root_uuids_to_delete)

    query = await DeleteAfterTimeQuery.init(db=db, timestamp=start_time)
    await query.execute(db=db)
