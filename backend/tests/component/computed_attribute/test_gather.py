from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub import config
from infrahub.computed_attribute.gather import (
    gather_trigger_computed_attribute_jinja2,
    gather_trigger_computed_attribute_python,
)
from infrahub.computed_attribute.models import ComputedAttrPythonQueryTriggerDefinition
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.constants import NODE_ORIGIN_LABEL, NodeMutationOrigin
from tests.helpers.trigger import branches_covered_by

TRANSFORM_NAME = "transform_person_cars"

# TestPerson.cars peers with the TestCar generic, whose members are TestElectricCar and TestGazCar.
# Only TestElectricCar is read through, so the other kinds behind the generic contribute no field.
QUERY_THROUGH_GENERIC = """
query PersonCars($id: ID!) {
    TestPerson(ids: [$id]) {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            ... on TestElectricCar {
                                nbr_engine { value }
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

QUERY_THROUGH_GENERIC_DISPLAY_LABEL = """
query PersonCars($id: ID!) {
    TestPerson(ids: [$id]) {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            display_label
                        }
                    }
                }
            }
        }
    }
}
"""

QUERY_THROUGH_GENERIC_HFID = """
query PersonCars($id: ID!) {
    TestPerson(ids: [$id]) {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            hfid
                        }
                    }
                }
            }
        }
    }
}
"""


async def _setup_person_transform(
    db: InfrahubDatabase,
    default_branch: Branch,
    schema_dict: dict[str, Any],
    query: str,
) -> None:
    """Give TestPerson a Python computed attribute fed by a transform that runs `query`."""
    gql_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=default_branch)
    await gql_query.new(db=db, name="person_cars", query=query)
    await gql_query.save(db=db)

    repository = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    await repository.new(
        db=db,
        name="repo_generics",
        ref=default_branch.name,
        commit="commit01",
        location="location01",
        queries=[gql_query],
    )
    await repository.save(db=db)

    transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON, branch=default_branch)
    await transform.new(
        db=db,
        name=TRANSFORM_NAME,
        file_path="transform.py",
        class_name="Transform",
        query=gql_query,
        repository=repository,
    )
    await transform.save(db=db)

    schema_dict = deepcopy(schema_dict)
    person = next(node for node in schema_dict["nodes"] if node["name"] == "Person")
    person["attributes"].append(
        {
            "name": "computed_desc_python",
            "kind": "Text",
            "read_only": True,
            "optional": True,
            "computed_attribute": {
                "kind": ComputedAttributeKind.TRANSFORM_PYTHON.value,
                "transform": TRANSFORM_NAME,
            },
        }
    )
    registry.schema.register_schema(schema=SchemaRoot(**schema_dict), branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)


def _triggers_by_kind(
    triggers: list[ComputedAttrPythonQueryTriggerDefinition],
) -> dict[str, ComputedAttrPythonQueryTriggerDefinition]:
    return {trigger.trigger.match["infrahub.node.kind"]: trigger for trigger in triggers}


async def test_gather_trigger_computed_attribute_jinja2_empty(register_core_models_schema: SchemaBranch) -> None:
    triggers = await gather_trigger_computed_attribute_jinja2()
    assert len(triggers) == 0


async def test_gather_trigger_computed_attribute_jinja2_only_main(car_person_schema_computed_attr: None) -> None:
    triggers = await gather_trigger_computed_attribute_jinja2()
    assert len(triggers) == 1
    trigger = triggers[0]
    assert trigger.name == "TestCar_computed_desc::kind::TestCar"
    assert trigger.generate_name() == "computed_attr_jinja2::main::TestCar_computed_desc::kind::TestCar"
    assert "infrahub.branch.name" not in trigger.trigger.match


async def test_gather_trigger_computed_attribute_jinja2_different_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_computed_attr: None
) -> None:
    branch = await create_branch(branch_name="branch2", db=db)

    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    car_schema = schema_branch.get_node("TestCar")

    attr1 = car_schema.get_attribute(name="computed_desc")
    attr1.computed_attribute.jinja2_template = (
        "{{ name__value | upper }} {{ owner__name__value | upper }} has {{ nbr_seats__value | upper }} seats"
    )
    schema_branch.set(name="TestCar", schema=car_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    branch.update_schema_hash()
    schema_branch.process()
    await branch.save(db=db)

    name_main = "computed_attr_jinja2::main::TestCar_computed_desc::kind::TestCar"
    name_branch_first = "computed_attr_jinja2::branch2::TestCar_computed_desc::kind::TestCar"
    name_branch_second = "computed_attr_jinja2::branch2::TestCar_computed_desc::kind::TestPerson"

    triggers = await gather_trigger_computed_attribute_jinja2()
    triggers_by_name = {trigger.generate_name(): trigger for trigger in triggers}
    assert set(triggers_by_name.keys()) == {name_main, name_branch_first, name_branch_second}

    trigger_main = triggers_by_name[name_main]
    assert "infrahub.branch.name" not in trigger_main.trigger.match
    assert {
        "prefect.resource.role": "infrahub.branch",
        "infrahub.resource.label": "!branch2",
    } in trigger_main.trigger.match_related

    trigger_branch = triggers_by_name[name_branch_first]
    assert "infrahub.branch.name" in trigger_branch.trigger.match
    assert trigger_branch.trigger.match["infrahub.branch.name"] == "branch2"

    trigger_branch = triggers_by_name[name_branch_second]
    assert "infrahub.branch.name" in trigger_branch.trigger.match
    assert trigger_branch.trigger.match["infrahub.branch.name"] == "branch2"


async def test_gather_trigger_computed_attribute_python(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_computed_attr: None, transform01: Node
) -> None:
    triggers, trigger_queries = await gather_trigger_computed_attribute_python(db=db)
    assert triggers

    trigger = triggers[0]
    assert trigger.name == "TestCar_computed_desc_python"

    triggers_by_kind = _triggers_by_kind(trigger_queries)
    assert set(triggers_by_kind) == {"TestCar"}
    assert triggers_by_kind["TestCar"].trigger.match_related["infrahub.field.name"] == ["name"]


async def test_two_attributes_sharing_a_transform_each_get_an_automation(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_computed_attr: None,
    transform01: Node,
) -> None:
    """One transform can feed several attributes, and each one needs its own automation.

    They share a query, so nothing else fires for the attribute left out.
    """
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get_node("TestCar")
    car_schema.attributes.append(
        AttributeSchema(
            name="computed_desc_python_second",
            kind="Text",
            read_only=True,
            optional=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                transform="transform01",
            ),
        )
    )
    schema_branch.set(name="TestCar", schema=car_schema)
    registry.schema.set_schema_branch(name=default_branch.name, schema=schema_branch)
    default_branch.update_schema_hash()
    schema_branch.process()
    await default_branch.save(db=db)

    triggers, trigger_queries = await gather_trigger_computed_attribute_python(db=db)

    assert {trigger.name for trigger in triggers} == {
        "TestCar_computed_desc_python",
        "TestCar_computed_desc_python_second",
    }
    assert {trigger.name for trigger in trigger_queries} == {
        "TestCar_computed_desc_python::kind::TestCar",
        "TestCar_computed_desc_python_second::kind::TestCar",
    }


async def test_gather_trigger_computed_attribute_python_only_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    transform01: Node,
) -> None:
    """Test that gather_trigger_computed_attribute_python handles the case where.

    a computed attribute only exists on a branch (not on main).

    """
    # Create a branch
    branch = await create_branch(branch_name="branch_with_computed_attr", db=db)

    # Add computed attribute to the schema ONLY on the branch
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    car_schema = schema_branch.get_node("TestCar")
    car_schema.attributes.append(
        AttributeSchema(
            name="computed_desc",
            kind="Text",
            read_only=True,
            optional=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                transform="transform01",
            ),
        )
    )
    schema_branch.set(name="TestCar", schema=car_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    branch.update_schema_hash()
    schema_branch.process()
    await branch.save(db=db)

    # This should not raise a KeyError
    triggers, _ = await gather_trigger_computed_attribute_python(db=db)

    # Verify we got triggers for the branch only
    assert len(triggers) == 1
    trigger = triggers[0]
    assert trigger.name == "TestCar_computed_desc"
    assert trigger.branch == "branch_with_computed_attr"


async def test_a_branch_that_repoints_a_transform_keeps_its_own_automation(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_computed_attr: None,
    transform01: Node,
    repo01: Node,
) -> None:
    """A branch can point an attribute at another transform, which reads other fields.

    Both transforms sit in the same repository, so the commit is equal on the two branches and
    nothing but the transform separates them. The branch still needs its own field filter.
    """
    seats_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=default_branch)
    await seats_query.new(
        db=db,
        name="query_seats",
        query="query { TestCar { edges { node { nbr_seats { value } } } } }",
        models=["TestCar"],
    )
    await seats_query.save(db=db)

    seats_transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON, branch=default_branch)
    await seats_transform.new(
        db=db,
        name="transform_seats",
        file_path="transform.py",
        class_name="Transform",
        query=seats_query,
        repository=repo01,
    )
    await seats_transform.save(db=db)

    branch = await create_branch(branch_name="branch_with_other_transform", db=db)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    car_schema = schema_branch.get_node("TestCar")
    car_schema.get_attribute(name="computed_desc_python").computed_attribute.transform = "transform_seats"
    schema_branch.set(name="TestCar", schema=car_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    branch.update_schema_hash()
    schema_branch.process()
    await branch.save(db=db)

    triggers, trigger_queries = await gather_trigger_computed_attribute_python(db=db)

    assert {trigger.generate_name() for trigger in triggers} == {
        "computed_attr_python::main::TestCar_computed_desc_python",
        "computed_attr_python::branch_with_other_transform::TestCar_computed_desc_python",
    }
    assert {
        (trigger.branch, tuple(sorted(trigger.trigger.match_related["infrahub.field.name"])))
        for trigger in trigger_queries
    } == {
        ("main", ("name",)),
        ("branch_with_other_transform", ("nbr_seats",)),
    }


async def test_gather_trigger_computed_attribute_python_fires_once_per_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_computed_attr: None,
    transform01: Node,
) -> None:
    """Each branch pinned to its own repository commit owns its automation.

    The default-branch automation must skip both, and still cover a branch created later.
    """
    for index, branch_name in enumerate(["branch1", "branch2"], start=1):
        branch = await create_branch(branch_name=branch_name, db=db)
        repositories = await NodeManager.query(
            db=db,
            schema=InfrahubKind.READONLYREPOSITORY,
            branch=branch,
            filters={"name__value": "repo02"},
        )
        repositories[0].commit.value = f"commit-branch{index}"
        await repositories[0].save(db=db)

    triggers, trigger_queries = await gather_trigger_computed_attribute_python(db=db)

    expected_owners = {
        "main": ["main"],
        "branch1": ["branch1"],
        "branch2": ["branch2"],
        "branch-created-after-setup": ["main"],
    }
    branch_names = list(expected_owners.keys())

    for definitions in (triggers, trigger_queries):
        triggers_by_scope = {definition.branch: definition for definition in definitions}
        assert set(triggers_by_scope) == {"main", "branch1", "branch2"}
        assert (
            branches_covered_by(
                triggers_by_scope=triggers_by_scope, kind="TestCar", field="name", branch_names=branch_names
            )
            == expected_owners
        )


async def test_python_triggers_match_only_live_origin(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_computed_attr: None, transform01: Node
) -> None:
    """A merge, a rebase or a coalesced write starts no per-node flow while the pass owns them.

    Both trigger families have to carry the filter: the owner one reaches the node that changed,
    the query one reaches its readers, and either would replay the whole change set on its own.
    """
    triggers, trigger_queries = await gather_trigger_computed_attribute_python(db=db)

    # Named, so that a gather returning nothing cannot satisfy the assertions below.
    assert [trigger.name for trigger in triggers] == ["TestCar_computed_desc_python"]
    assert [trigger.name for trigger in trigger_queries] == ["TestCar_computed_desc_python::kind::TestCar"]

    for trigger in [*triggers, *trigger_queries]:
        assert trigger.trigger.match[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE.value


async def test_python_triggers_keep_every_origin_when_the_pass_is_disabled(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_computed_attr: None,
    transform01: Node,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabling the coalesced pass hands merge and rebase back to the per-node automations.

    One setting decides both halves, so the system can never sit with the filter applied and
    nothing left to recompute a replayed change.
    """
    monkeypatch.setattr(config.SETTINGS.main, "coalesce_python_recompute_after_merge", False)

    triggers, trigger_queries = await gather_trigger_computed_attribute_python(db=db)

    # Named, so that a gather returning nothing cannot satisfy the assertions below.
    assert [trigger.name for trigger in triggers] == ["TestCar_computed_desc_python"]
    assert [trigger.name for trigger in trigger_queries] == ["TestCar_computed_desc_python::kind::TestCar"]

    for trigger in [*triggers, *trigger_queries]:
        assert NODE_ORIGIN_LABEL not in trigger.trigger.match


@dataclass
class QueryTriggerCase:
    name: str
    query: str
    expected_fields_by_kind: dict[str, list[str]]


QUERY_TRIGGER_CASES = [
    QueryTriggerCase(
        name="unread_kind_behind_a_generic_gets_no_trigger",
        query=QUERY_THROUGH_GENERIC,
        expected_fields_by_kind={"TestPerson": ["cars", "name"], "TestElectricCar": ["nbr_engine"]},
    ),
    QueryTriggerCase(
        name="display_label_is_matched_as_a_field",
        query=QUERY_THROUGH_GENERIC_DISPLAY_LABEL,
        expected_fields_by_kind={
            "TestPerson": ["cars", "name"],
            "TestCar": ["display_label"],
            "TestElectricCar": ["display_label"],
            "TestGazCar": ["display_label"],
        },
    ),
    QueryTriggerCase(
        name="hfid_is_matched_under_its_schema_name",
        query=QUERY_THROUGH_GENERIC_HFID,
        expected_fields_by_kind={
            "TestPerson": ["cars", "name"],
            "TestCar": ["human_friendly_id"],
            "TestElectricCar": ["human_friendly_id"],
            "TestGazCar": ["human_friendly_id"],
        },
    ),
]


@pytest.mark.parametrize("case", QUERY_TRIGGER_CASES, ids=lambda case: case.name)
async def test_gather_trigger_computed_attribute_python_query(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics_unregistered: dict[str, Any],
    case: QueryTriggerCase,
) -> None:
    """The read set of the query decides which kinds get a trigger and which fields it matches.

    A kind the query reads no field from gets none at all: with nothing to filter on, the trigger
    would fire on every update to that kind and recompute a value those updates cannot change.
    """
    await _setup_person_transform(
        db=db,
        default_branch=default_branch,
        schema_dict=car_person_schema_generics_unregistered,
        query=case.query,
    )

    _, trigger_queries = await gather_trigger_computed_attribute_python(db=db)

    assert {
        kind: sorted(trigger.trigger.match_related["infrahub.field.name"])
        for kind, trigger in _triggers_by_kind(trigger_queries).items()
    } == {kind: sorted(fields) for kind, fields in case.expected_fields_by_kind.items()}
