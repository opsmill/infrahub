from infrahub.core import utils
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.telemetry.database import gather_database_information, get_server_info, get_system_info


async def test_get_server_info(db: InfrahubDatabase) -> None:
    servers = await get_server_info(db)
    assert len(servers) == 1


async def test_get_system_info(db: InfrahubDatabase) -> None:
    system_info = await get_system_info(db)
    assert system_info is not None


async def test_gather_database_information(db: InfrahubDatabase) -> None:
    data = await gather_database_information.fn(db)
    assert data is not None


async def test_gather_database_information_corenode_matches_seeded(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    """``node_count["corenode"]`` equals an independently-computed managed-node count exactly.

    ``corenode`` goes through the branch/temporal-correct count path. The seeded
    ``TestPerson`` nodes carry the ``CoreNode`` generic label (their namespace is neither
    ``Schema`` nor ``Internal``), so an independent raw label count is the oracle: the count
    the gather reports must match it to the node, and the raw vertex ``total`` must be left
    untouched and never smaller than the managed-node subset.
    """
    # Baseline of pre-existing managed nodes via a raw label count — a different code path
    # from NodeManager.count — so the assertion holds regardless of any nodes already present.
    baseline_corenode = await utils.count_nodes(db=db, label=InfrahubKind.NODE)

    seeded = 5
    for index in range(seeded):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person.new(db=db, name=f"person-{index}")
        await person.save(db=db)

    expected_corenode = baseline_corenode + seeded
    # Independent oracle: raw CoreNode-label vertex count after seeding (not NodeManager.count).
    independent_corenode = await utils.count_nodes(db=db, label=InfrahubKind.NODE)
    assert independent_corenode == expected_corenode

    data = await gather_database_information.fn(db)

    assert data.node_count["corenode"] == expected_corenode
    # Raw vertex total stays as-is and always contains at least the managed-node subset.
    assert data.node_count["total"] == await utils.count_nodes(db=db)
    assert data.node_count["total"] >= data.node_count["corenode"]
