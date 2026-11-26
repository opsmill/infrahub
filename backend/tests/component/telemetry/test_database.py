from typing import Any
from uuid import uuid4

from neo4j import Record

from infrahub.core import utils
from infrahub.core.branch import Branch
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query import QueryType
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.telemetry.database import (
    count_user_nodes,
    gather_database_information,
    get_server_info,
    get_system_info,
)
from tests.helpers.db_query_failer import FailingQueryInfrahubDatabase, InjectedQueryError

from .conftest import create_artifact, create_generated_artifact, create_generator_instance


async def test_get_server_info(db: InfrahubDatabase) -> None:
    servers = await get_server_info(db)
    assert len(servers) == 1


async def test_get_system_info(db: InfrahubDatabase) -> None:
    system_info = await get_system_info(db)
    assert system_info is not None


async def test_gather_database_information(db: InfrahubDatabase) -> None:
    data = await gather_database_information.fn(db)
    assert data is not None


async def test_gather_database_information_survives_system_info_failure(db: InfrahubDatabase) -> None:
    """A failed system-information read reports ``system_info`` as ``None`` and keeps the rest of the snapshot."""
    failing_db = FailingQueryInfrahubDatabase.from_db(db=db, failing_query_names={"get_system_info"})

    data = await gather_database_information.fn(failing_db)

    assert data.system_info is None
    assert isinstance(data.servers, list)
    assert data.node_count["total"] is not None
    assert data.relationship_count["total"] is not None


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


_OUTPUT_TOTALS = ("with_artifact", "with_generated_artifact", "generated_artifact", "with_generator_instance")


class FailingContentReadDatabase(FailingQueryInfrahubDatabase):
    """Database that fails the count of nodes with an output only when the count reads stored content."""

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        if name == "count-nodes-with-output" and params is not None and "content_attribute" in params:
            raise InjectedQueryError("The read of stored content failed on purpose")
        return await super().execute_query_with_metadata(
            query=query, params=params, name=name, context=context, type=type, timeout_seconds=timeout_seconds
        )


async def _delete(db: InfrahubDatabase, node: Node) -> None:
    current = await NodeManager.get_one(db=db, id=node.id, raise_on_error=True)
    await current.delete(db=db)


async def test_gather_database_information_artifact_totals(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    artifact_definition: Node,
) -> None:
    """The artifact totals count each node once, on the default branch, and split out stored content."""
    cars = car_person_data_generic

    baseline = await gather_database_information.fn(db)
    # The four seeded cars are the only nodes whose kind can have an artifact.
    assert baseline.node_count["artifact_target"] == 4
    assert {key: baseline.node_count[key] for key in _OUTPUT_TOTALS} == dict.fromkeys(_OUTPUT_TOTALS, 0)

    # Two artifacts with stored content on one node: one node, two artifacts.
    await create_generated_artifact(db=db, definition=artifact_definition, target=cars["c1"], name="c1-a")
    await create_generated_artifact(db=db, definition=artifact_definition, target=cars["c1"], name="c1-b")
    # An artifact whose first generation has not stored content yet.
    await create_artifact(db=db, definition=artifact_definition, target=cars["c2"], name="c2-a", status="Pending")
    # A deleted artifact.
    deleted_artifact = await create_generated_artifact(
        db=db, definition=artifact_definition, target=cars["c3"], name="c3-a"
    )
    await _delete(db=db, node=deleted_artifact)
    # An artifact generated on another branch only.
    other_branch = await create_branch(branch_name="artifact-branch", db=db)
    await create_generated_artifact(
        db=db, definition=artifact_definition, target=cars["c4"], name="c4-a", branch=other_branch
    )
    # A node deleted after its artifact was generated.
    deleted_car = await Node.init(db=db, schema="TestGazCar", branch=default_branch)
    await deleted_car.new(db=db, name="scrapped", nbr_seats=2, mpg=20, owner=cars["p1"])
    await deleted_car.save(db=db)
    await create_generated_artifact(db=db, definition=artifact_definition, target=deleted_car, name="scrapped-a")
    await _delete(db=db, node=deleted_car)
    # An artifact whose latest generation failed still holds the content of an earlier generation.
    failed_car = await Node.init(db=db, schema="TestGazCar", branch=default_branch)
    await failed_car.new(db=db, name="stalled", nbr_seats=2, mpg=20, owner=cars["p1"])
    await failed_car.save(db=db)
    await create_artifact(
        db=db,
        definition=artifact_definition,
        target=failed_car,
        name="stalled-a",
        status="Error",
        storage_id=str(uuid4()),
        checksum=str(uuid4()),
    )

    data = await gather_database_information.fn(db)

    assert data.node_count["artifact_target"] == 5
    assert data.node_count["with_artifact"] == 3
    assert data.node_count["with_generated_artifact"] == 2
    assert data.node_count["generated_artifact"] == 3
    assert data.node_count["with_generator_instance"] == 0


async def test_gather_database_information_generator_instance_total(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    generator_definitions: list[Node],
) -> None:
    """A node with a generator instance is counted once, whatever the status of the instance."""
    cars = car_person_data_generic
    first_definition, second_definition = generator_definitions

    # Instances of two generator definitions for one node: one node.
    await create_generator_instance(db=db, definition=first_definition, target=cars["c1"])
    await create_generator_instance(db=db, definition=second_definition, target=cars["c1"])
    # The instance exists from the start of the first run, so a run that failed still counts.
    await create_generator_instance(
        db=db, definition=first_definition, target=cars["c2"], status=GeneratorInstanceStatus.ERROR
    )
    # A deleted instance.
    deleted_instance = await create_generator_instance(db=db, definition=first_definition, target=cars["c3"])
    await _delete(db=db, node=deleted_instance)
    # An instance created on another branch only.
    other_branch = await create_branch(branch_name="generator-branch", db=db)
    await create_generator_instance(db=db, definition=first_definition, target=cars["c4"], branch=other_branch)

    data = await gather_database_information.fn(db)

    assert data.node_count["with_generator_instance"] == 2
    assert data.node_count["with_artifact"] == 0
    assert data.node_count["with_generated_artifact"] == 0
    assert data.node_count["generated_artifact"] == 0


async def test_gather_database_information_survives_output_count_failure(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """A failed read of the artifacts and generator instances reports their totals as ``None`` and keeps the rest."""
    failing_db = FailingQueryInfrahubDatabase.from_db(db=db, failing_query_names={"count-nodes-with-output"})

    data = await gather_database_information.fn(failing_db)

    assert {key: data.node_count[key] for key in _OUTPUT_TOTALS} == dict.fromkeys(_OUTPUT_TOTALS)
    # With the core schema only, no kind can have an artifact.
    assert data.node_count["artifact_target"] == 0
    assert data.node_count["corenode"] is not None
    assert data.node_count["user"] is not None


async def test_gather_database_information_failed_artifact_read_nulls_only_the_artifact_totals(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    generator_definitions: list[Node],
) -> None:
    await create_generator_instance(db=db, definition=generator_definitions[0], target=car_person_data_generic["c1"])
    failing_db = FailingContentReadDatabase.from_db(db=db, failing_query_names=set())

    data = await gather_database_information.fn(failing_db)

    assert {key: data.node_count[key] for key in _OUTPUT_TOTALS} == {
        "with_artifact": None,
        "with_generated_artifact": None,
        "generated_artifact": None,
        "with_generator_instance": 1,
    }
    assert data.node_count["artifact_target"] == 4
