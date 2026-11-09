from infrahub.core import utils
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.telemetry.database import (
    count_user_nodes,
    gather_database_information,
    get_server_info,
    get_system_info,
)


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
    """``corenode`` matches an independently-computed managed-node count exactly.

    The oracle is a raw ``CoreNode``-label count — a different code path from the gather's
    ``NodeManager.count`` — and the raw ``total`` must stay untouched and never below the subset.
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


async def test_gather_database_information_user_counts_only_user_namespaces(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    """``user`` counts only user-defined-namespace nodes, excluding Core.

    A seeded ``CoreAccount`` (restricted ``Core`` namespace) is a managed ``CoreNode`` but must
    not be counted by ``user`` — forcing ``user < corenode`` and proving Core is excluded, while
    ``user`` ⊆ ``corenode`` ⊆ ``total`` still holds.
    """
    # With only the user-editable Test namespace registered and no user nodes yet, the gather
    # reports zero user nodes — the independent baseline the seeded count is measured against.
    baseline = await gather_database_information.fn(db)
    assert baseline.node_count["user"] == 0

    seeded_users = 4
    for index in range(seeded_users):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person.new(db=db, name=f"user-person-{index}")
        await person.save(db=db)

    # A single Core management node: a CoreNode that lives outside every user-editable namespace.
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT, branch=default_branch)
    await account.new(db=db, name="core-account", account_type="User", password="accountPassword123")
    await account.save(db=db)

    data = await gather_database_information.fn(db)

    # Exactly the seeded user nodes are counted; the Core account is not.
    assert data.node_count["user"] == seeded_users

    # All three counts are populated in this scenario; None is only reported on a count fallback.
    user_count = data.node_count["user"]
    corenode_count = data.node_count["corenode"]
    total_count = data.node_count["total"]
    assert user_count is not None
    assert corenode_count is not None
    assert total_count is not None

    # Strict nesting: user ⊆ corenode ⊆ total.
    assert user_count <= corenode_count <= total_count
    # The Core account is a managed node excluded from user, so user is strictly below corenode.
    assert user_count < corenode_count


async def test_count_user_nodes_is_branch_aware(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    """``user`` reflects the default branch at gather time: deleted and branch-only nodes are excluded."""
    assert await count_user_nodes(db=db) == 0

    persons: list[Node] = []
    for index in range(3):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person.new(db=db, name=f"branch-aware-person-{index}")
        await person.save(db=db)
        persons.append(person)

    # A node deleted on the default branch stops being counted.
    await persons[0].delete(db=db)

    # A node that exists only on another branch is invisible to the default-branch count.
    other_branch = await create_branch(branch_name="user-count-branch", db=db)
    branch_person = await Node.init(db=db, schema="TestPerson", branch=other_branch)
    await branch_person.new(db=db, name="branch-only-person")
    await branch_person.save(db=db)

    assert await count_user_nodes(db=db) == 2


async def test_count_user_nodes_matches_per_kind_oracle(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    """The single-pass count equals summing a per-kind branch-aware count over the same kinds."""
    seeded_persons = 3
    persons: list[Node] = []
    for index in range(seeded_persons):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person.new(db=db, name=f"oracle-person-{index}", height=180)
        await person.save(db=db)
        persons.append(person)

    seeded_cars = 2
    for index in range(seeded_cars):
        car = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await car.new(db=db, name=f"oracle-car-{index}", nbr_seats=4, is_electric=False, owner=persons[0])
        await car.save(db=db)

    schema_branch = db.schema.get_schema_branch(name=default_branch.name)
    user_namespaces = [namespace.name for namespace in schema_branch.get_namespaces() if namespace.user_editable]
    oracle = 0
    for node_schema in schema_branch.get_schemas_for_namespaces(namespaces=user_namespaces):
        if isinstance(node_schema, NodeSchema) and InfrahubKind.GENERICGROUP not in node_schema.inherit_from:
            oracle += await NodeManager.count(db=db, schema=node_schema.kind, branch=default_branch)

    assert oracle == seeded_persons + seeded_cars
    assert await count_user_nodes(db=db) == oracle
