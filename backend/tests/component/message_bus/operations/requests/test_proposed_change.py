from uuid import uuid4

import pytest
import ujson
from fast_depends import Provider
from infrahub_sdk.diff import NodeDiff
from pytest_httpx import HTTPXMock

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, InfrahubKind, RelationshipCardinality, RelationshipKind, SchemaPathType
from infrahub.core.diff.model.diff import DiffElementType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.types import ProposedChangeBranchDiff
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestProposedChangeSchemaIntegrity
from infrahub.proposed_change.tasks import (
    _get_proposed_change_schema_integrity_constraints,
    run_proposed_change_schema_integrity_check,
)
from infrahub.workers.dependencies import build_cache
from tests.adapters.cache import MemoryCache
from tests.conftest import TestHelper

# Only intercept the fake SDK endpoint: the per-worker Prefect server flushes
# batched API logs on its own schedule, and a flush landing mid-test must reach
# the real server instead of tripping the mock's unmatched-request teardown check.
pytestmark = pytest.mark.httpx_mock(should_mock=lambda request: request.url.host == "mock")

SOURCE_BRANCH_A = "branch2"
DST_BRANCH_A = "main"


@pytest.fixture
async def mock_schema_query_02(helper: TestHelper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = (helper.get_fixtures_dir() / "schemas" / "schema_02.json").read_text(encoding="UTF-8")

    httpx_mock.add_response(method="GET", url="http://mock/api/schema?branch=main", json=ujson.loads(response_text))
    return httpx_mock


@pytest.fixture
def branch_diff_01() -> ProposedChangeBranchDiff:
    return ProposedChangeBranchDiff(
        pipeline_id=uuid4(),
        repositories=[],
    )


@pytest.fixture
def branch_diff_01_summary() -> list[NodeDiff]:
    return [
        {
            "branch": "branch2",
            "action": "updated",
            "kind": "TestPerson",
            "id": "11111111-1111-1111-1111-111111111111",
            "display_label": "",
            "elements": [
                {
                    "name": "name",
                    "element_type": DiffElementType.ATTRIBUTE.name,
                    "action": DiffAction.UPDATED.value,
                    "summary": {"added": 0, "updated": 1, "removed": 0},
                }
            ],
        },
        {
            "branch": "main",
            "action": "updated",
            "kind": "TestPerson",
            "id": "22222222-2222-2222-2222-222222222222",
            "display_label": "",
            "elements": [
                {
                    "name": "height",
                    "element_type": DiffElementType.ATTRIBUTE.name,
                    "action": DiffAction.UPDATED.value,
                    "summary": {"added": 0, "updated": 1, "removed": 0},
                },
                {
                    "name": "cars",
                    "element_type": DiffElementType.RELATIONSHIP_MANY.name,
                    "action": DiffAction.UPDATED.value,
                    "summary": {"added": 0, "updated": 1, "removed": 0},
                    "peers": [
                        {"action": DiffAction.REMOVED.value, "summary": {"added": 0, "updated": 0, "removed": 1}},
                        {"action": DiffAction.ADDED.value, "summary": {"added": 1, "updated": 0, "removed": 0}},
                    ],
                },
            ],
        },
    ]


@pytest.fixture
async def branch2(db: InfrahubDatabase) -> Branch:
    return await create_branch(branch_name=SOURCE_BRANCH_A, db=db)


@pytest.fixture
async def schema_integrity_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    branch_diff_01: ProposedChangeBranchDiff,
) -> RequestProposedChangeSchemaIntegrity:
    obj = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE, branch=default_branch)
    await obj.new(db=db, name="pc1", source_branch=SOURCE_BRANCH_A, destination_branch="main")
    await obj.save(db=db)

    return RequestProposedChangeSchemaIntegrity(
        proposed_change=obj.id,
        source_branch=SOURCE_BRANCH_A,
        source_branch_sync_with_git=False,
        destination_branch="main",
        branch_diff=branch_diff_01,
    )


async def test_get_proposed_change_schema_integrity_constraints(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    schema_integrity_01: RequestProposedChangeSchemaIntegrity,
    branch_diff_01_summary: list[NodeDiff],
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    constraints = await _get_proposed_change_schema_integrity_constraints(
        db=db, schema=schema, diff_summary=branch_diff_01_summary, branch=default_branch
    )
    # the diff changes name on one TestPerson and height+cars on another; only name participates in
    # uniqueness, so the uniqueness check is scoped to just the node that changed name, while every
    # field-level check spans the population (node_uuids=None)
    name_changed_person_uuids = ("11111111-1111-1111-1111-111111111111",)
    actual = {
        (
            c.constraint_name,
            c.path.schema_kind,
            c.path.field_name,
            c.path.property_name,
            c.path.path_type,
            tuple(c.node_uuids) if c.node_uuids is not None else None,
        )
        for c in constraints
    }
    assert actual == {
        ("attribute.kind.update", "TestPerson", "name", "kind", SchemaPathType.ATTRIBUTE, None),
        ("attribute.kind.update", "TestPerson", "height", "kind", SchemaPathType.ATTRIBUTE, None),
        ("attribute.optional.update", "TestPerson", "name", "optional", SchemaPathType.ATTRIBUTE, None),
        ("attribute.optional.update", "TestPerson", "height", "optional", SchemaPathType.ATTRIBUTE, None),
        ("attribute.unique.update", "TestPerson", "name", "unique", SchemaPathType.ATTRIBUTE, None),
        ("attribute.unique.update", "TestPerson", "height", "unique", SchemaPathType.ATTRIBUTE, None),
        ("relationship.optional.update", "TestPerson", "cars", "optional", SchemaPathType.RELATIONSHIP, None),
        ("relationship.peer.update", "TestPerson", "cars", "peer", SchemaPathType.RELATIONSHIP, None),
        ("relationship.cardinality.update", "TestPerson", "cars", "cardinality", SchemaPathType.RELATIONSHIP, None),
        ("relationship.min_count.update", "TestPerson", "cars", "min_count", SchemaPathType.RELATIONSHIP, None),
        ("relationship.max_count.update", "TestPerson", "cars", "max_count", SchemaPathType.RELATIONSHIP, None),
        (
            "node.uniqueness_constraints.update",
            "TestPerson",
            "uniqueness_constraints",
            "uniqueness_constraints",
            SchemaPathType.NODE,
            name_changed_person_uuids,
        ),
    }


async def test_schema_integrity(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    schema_integrity_01: RequestProposedChangeSchemaIntegrity,
    branch_diff_01_summary: list[NodeDiff],
    dependency_provider: Provider,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main: Node,
) -> None:
    cache = MemoryCache()
    with dependency_provider.scope(build_cache, lambda: cache):
        branch2 = await create_branch(branch_name=SOURCE_BRANCH_A, db=db)

        person = await Node.init(db=db, schema="TestPerson", branch=branch2)
        await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
        await person.save(db=db)
        person_john = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)

        branch2_schema = registry.schema.get_schema_branch(name=branch2.name)
        person_schema = branch2_schema.get(name="TestPerson")
        name_attr = person_schema.get_attribute(name="name")
        name_attr.parameters.regex = r"^[A-Z]+$"
        branch2_schema.set(name="TestPerson", schema=person_schema)

        await set_diff_summary_cache(
            pipeline_id=schema_integrity_01.branch_diff.pipeline_id, diff_summary=branch_diff_01_summary, cache=cache
        )

        await run_proposed_change_schema_integrity_check(model=schema_integrity_01)

        checks = await registry.manager.query(db=db, schema=InfrahubKind.SCHEMACHECK)
        assert len(checks) == 2
        assert checks[0].conclusion.value.value == "failure"
        assert checks[1].conclusion.value.value == "failure"

        all_conflicts = [c.conflicts.value for c in checks]
        assert [
            {
                "branch": "placeholder",
                "id": person_john_main.id,
                "kind": "TestPerson",
                "name": "schema/TestPerson/name/parameters.regex",
                "path": "schema/TestPerson/name/parameters.regex",
                "type": ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
                "value": (
                    f"Attribute-level 'regex' constraint violation on schema 'TestPerson'. Node (TestPerson: {person_john_main.id})"
                    f" is not compliant. The error relates to field name='{person_john_main.name.value}'."
                ),
            }
        ] in all_conflicts
        assert [
            {
                "branch": "placeholder",
                "id": person_john_main.id,
                "kind": "TestPerson",
                "name": "schema/TestPerson/name/kind",
                "path": "schema/TestPerson/name/kind",
                "type": "attribute.kind.update",
                "value": (
                    f"Attribute-level 'kind' constraint violation on schema 'TestPerson'. Node (TestPerson: {person_john_main.id})"
                    f" is not compliant. The error relates to field name='{person_john_main.name.value}'."
                ),
            }
        ] in all_conflicts

        # verify integrity checks are removed after being fixed
        person_john.name.value = "JOHN"
        await person_john.save(db=db)

        await run_proposed_change_schema_integrity_check(model=schema_integrity_01)

        checks = await registry.manager.query(db=db, schema=InfrahubKind.SCHEMACHECK)
        assert len(checks) == 1
        assert checks[0].conclusion.value.value == "success"
        assert checks[0].conflicts.value == []


async def test_schema_integrity_process_validation_error(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    schema_integrity_01: RequestProposedChangeSchemaIntegrity,
    branch_diff_01_summary: list[NodeDiff],
    dependency_provider: Provider,
) -> None:
    cache = MemoryCache()
    with dependency_provider.scope(build_cache, lambda: cache):
        branch2 = await create_branch(branch_name=SOURCE_BRANCH_A, db=db)
        branch2_schema = registry.schema.get_schema_branch(name=branch2.name)
        person_schema = branch2_schema.get(name="TestPerson")
        person_schema.relationships.append(
            RelationshipSchema(
                name="name",
                peer="TestCar",
                cardinality=RelationshipCardinality.MANY,
                kind=RelationshipKind.ATTRIBUTE,
            )
        )
        branch2_schema.set(name="TestPerson", schema=person_schema)

        await set_diff_summary_cache(
            pipeline_id=schema_integrity_01.branch_diff.pipeline_id, diff_summary=branch_diff_01_summary, cache=cache
        )

        await run_proposed_change_schema_integrity_check(model=schema_integrity_01)

        checks = await registry.manager.query(db=db, schema=InfrahubKind.SCHEMACHECK)
        assert len(checks) == 1
        assert checks[0].conclusion.value.value == "failure"
        conflicts = checks[0].conflicts.value
        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "schema.process.validation"
        assert conflicts[0]["kind"] == "TestPerson"
        assert "unique" in conflicts[0]["value"].lower()
