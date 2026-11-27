from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.convert_object_type import ConversionFieldInput, ConversionFieldValue

from infrahub.core.constants import InfrahubKind
from infrahub.core.convert_object_type.object_conversion import convert_and_validate_object_type
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    HolderKey,
    HolderKind,
    OwnerOrigin,
    OwnerState,
    ResolvedOwnership,
    StoredOwnerState,
    field_holder,
)
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.mutations import convert_object_type as convert_object_type_mutation
from tests.helpers.graphql import graphql
from tests.helpers.ownership import SECONDS_TO_WAIT, wait_for_the_other_write

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_convert_object_type_with_profile_error(
    db: InfrahubDatabase, schemas_conversion: dict[str, Any], default_branch: Branch
) -> None:
    """Test that converting an object type with a profile returns the appropriate error message."""
    schema = SchemaRoot(**schemas_conversion)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    person1_profile = await Node.init(db=db, schema="ProfileTestconvPerson1")
    await person1_profile.new(db=db, profile_name="person1-profile", profile_priority=10, height=175)
    await person1_profile.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    create_person_mutation = f"""
    mutation {{
        TestconvPerson1Create(data: {{
            name: {{value: "John"}},
            profiles: [{{id: "{person1_profile.id}"}}]
        }}) {{
            ok
            object {{
                id
            }}
        }}
    }}
    """

    create_result = await graphql(
        schema=gql_params.schema,
        source=create_person_mutation,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert create_result.errors is None
    assert create_result.data
    assert create_result.data["TestconvPerson1Create"]["ok"] is True
    person1_node_id = create_result.data["TestconvPerson1Create"]["object"]["id"]

    mapping = {
        "name": ConversionFieldInput(source_field="name"),
        "age": ConversionFieldInput(data=ConversionFieldValue(attribute_value=30)),
    }
    mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}

    result = await graphql(
        schema=gql_params.schema,
        source=CONVERT_OBJECT_TYPE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "node_id": person1_node_id,
            "target_kind": "TestconvPerson2",
            "fields_mapping": mapping_dict,
        },
    )

    assert result.errors
    assert (
        "The attribute 'height' is from a profile, converting objects that use profiles is not yet supported."
        in str(result.errors)
    )


async def test_convert_object_type_already_converted_returns_not_found(
    db: InfrahubDatabase, schemas_conversion: dict[str, Any], default_branch: Branch
) -> None:
    """Re-converting a node whose id was consumed by a prior conversion reports a not-found error."""
    schema = SchemaRoot(**schemas_conversion)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    person1 = await Node.init(db=db, schema="TestconvPerson1")
    await person1.new(db=db, name="John")
    await person1.save(db=db)
    person1_node_id = person1.id

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    mapping = {
        "name": ConversionFieldInput(source_field="name"),
        "age": ConversionFieldInput(data=ConversionFieldValue(attribute_value=30)),
    }
    mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}

    first_result = await graphql(
        schema=gql_params.schema,
        source=CONVERT_OBJECT_TYPE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "node_id": person1_node_id,
            "target_kind": "TestconvPerson2",
            "fields_mapping": mapping_dict,
        },
    )

    assert first_result.errors is None
    assert first_result.data
    assert first_result.data["ConvertObjectType"]["ok"] is True

    second_result = await graphql(
        schema=gql_params.schema,
        source=CONVERT_OBJECT_TYPE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "node_id": person1_node_id,
            "target_kind": "TestconvPerson2",
            "fields_mapping": mapping_dict,
        },
    )

    assert second_result.errors
    assert [error.message for error in second_result.errors] == [
        f"Unable to find the node {person1_node_id} / Node in the database."
    ]


async def _write_owners(
    db: InfrahubDatabase, branch: Branch, node_id: str, states: dict[HolderKey, StoredOwnerState]
) -> None:
    repository = OwnershipRepository(db=db, branch=branch, at=None)
    for holder, state in states.items():
        await repository.write(
            node_id=node_id, holder=holder, state=state, write_branch=branch, at=Timestamp(), user_id="test-user-id"
        )


async def _convert_person(db: InfrahubDatabase, branch: Branch, node_id: str, fields_mapping: dict[str, Any]) -> str:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CONVERT_OBJECT_TYPE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"node_id": node_id, "target_kind": "TestconvPerson2", "fields_mapping": fields_mapping},
    )
    assert result.errors is None
    assert result.data
    return result.data["ConvertObjectType"]["node"]["id"]


async def test_convert_object_type_keeps_node_owners_and_sources(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schemas_conversion: dict[str, Any],
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**schemas_conversion), branch=default_branch.name)
    default_branch.update_schema_hash()
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="dc-emea")
    await group.save(db=db)
    new_ids: dict[str, str] = {}
    for name, owner_ids in {"with-owners": (group.id,), "without-owner": ()}.items():
        person = await Node.init(db=db, schema="TestconvPerson1")
        await person.new(db=db, name=name)
        await person.save(db=db)
        state = StoredOwnerState(owner_ids=owner_ids)
        await _write_owners(
            db=db, branch=default_branch, node_id=person.id, states={NODE_HOLDER: state, NODE_SOURCES_HOLDER: state}
        )

        new_ids[name] = await _convert_person(
            db=db,
            branch=default_branch,
            node_id=person.id,
            fields_mapping={"name": {"source_field": "name"}, "age": {"data": {"attribute_value": 30}}},
        )

    stored = await OwnershipRepository(db=db, branch=default_branch, at=None).read(node_ids=list(new_ids.values()))
    assert {
        name: (stored[node_id].get(NODE_HOLDER).owner_ids, stored[node_id].get(NODE_SOURCES_HOLDER).owner_ids)
        for name, node_id in new_ids.items()
    } == {"with-owners": ((group.id,), (group.id,)), "without-owner": ((), None)}


@pytest.mark.parametrize(
    "deleted",
    [pytest.param(("dc-emea",), id="one_owner_deleted"), pytest.param(("dc-emea", "dc-security"), id="all_deleted")],
)
async def test_convert_object_type_keeps_the_deleted_owners_of_the_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schemas_conversion: dict[str, Any],
    deleted: tuple[str, ...],
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**schemas_conversion), branch=default_branch.name)
    default_branch.update_schema_hash()
    groups: dict[str, Node] = {}
    for name in ("dc-emea", "dc-security"):
        groups[name] = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await groups[name].new(db=db, name=name)
        await groups[name].save(db=db)
    owner_ids = tuple(sorted(group.id for group in groups.values()))
    person = await Node.init(db=db, schema="TestconvPerson1")
    await person.new(db=db, name="deleted-owners")
    await person.save(db=db)
    await _write_owners(
        db=db, branch=default_branch, node_id=person.id, states={NODE_HOLDER: StoredOwnerState(owner_ids=owner_ids)}
    )
    for name in deleted:
        await groups[name].delete(db=db)

    new_id = await _convert_person(
        db=db,
        branch=default_branch,
        node_id=person.id,
        fields_mapping={"name": {"source_field": "name"}, "age": {"data": {"attribute_value": 30}}},
    )

    stored = await OwnershipRepository(db=db, branch=default_branch, at=None).read(node_ids=[new_id])
    assert stored[new_id].get(NODE_HOLDER) == StoredOwnerState(owner_ids=owner_ids)


async def test_convert_object_type_gives_the_owners_of_a_template_copy_as_own_owners(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schemas_conversion: dict[str, Any],
) -> None:
    nodes = [
        {**node, "generate_template": True} if node["name"] == "Person1" else node
        for node in schemas_conversion["nodes"]
    ]
    registry.schema.register_schema(
        schema=SchemaRoot(**{**schemas_conversion, "nodes": nodes}), branch=default_branch.name
    )
    default_branch.update_schema_hash()
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="dc-emea")
    await group.save(db=db)
    template = await Node.init(db=db, schema="TemplateTestconvPerson1")
    await template.new(db=db, template_name="person-template")
    await template.save(db=db)
    person = await Node.init(db=db, schema="TestconvPerson1")
    await person.new(db=db, name="template-copy")
    await person.save(db=db)
    name_holder = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name")
    copied = StoredOwnerState(owner_ids=(group.id,), template_id=template.id)
    await _write_owners(
        db=db, branch=default_branch, node_id=person.id, states={NODE_HOLDER: copied, name_holder: copied}
    )

    new_id = await _convert_person(
        db=db,
        branch=default_branch,
        node_id=person.id,
        fields_mapping={"name": {"source_field": "name"}, "age": {"data": {"attribute_value": 30}}},
    )

    repository = OwnershipRepository(db=db, branch=default_branch, at=None)
    stored = await repository.read(node_ids=[new_id], attributes=True)
    own = StoredOwnerState(owner_ids=(group.id,))
    assert dict(stored[new_id].holders) == {NODE_HOLDER: own, name_holder: own}
    assert await OwnershipResolver(repository=repository).resolve(node_ids=[new_id]) == {
        new_id: ResolvedOwnership(
            state=OwnerState.OWNERS, owner_ids=(group.id,), origin=OwnerOrigin.SELF, origin_node_id=new_id
        )
    }


async def test_convert_object_type_gives_the_owners_that_the_node_holds_when_its_transaction_starts(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schemas_conversion: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**schemas_conversion), branch=default_branch.name)
    default_branch.update_schema_hash()
    group_ids = []
    for name in ("dc-emea", "dc-security"):
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name=name)
        await group.save(db=db)
        group_ids.append(group.id)
    person = await Node.init(db=db, schema="TestconvPerson1")
    await person.new(db=db, name="owners-changed")
    await person.save(db=db)
    await _write_owners(
        db=db,
        branch=default_branch,
        node_id=person.id,
        states={NODE_HOLDER: StoredOwnerState(owner_ids=(group_ids[0],))},
    )
    convert = convert_object_type_mutation.convert_and_validate_object_type

    async def convert_after_another_write(**kwargs: Any) -> Node:
        # Another request changes the owners after the mutation read the node.
        await _write_owners(
            db=db,
            branch=default_branch,
            node_id=person.id,
            states={NODE_HOLDER: StoredOwnerState(owner_ids=(group_ids[1],))},
        )
        return await convert(**kwargs)

    monkeypatch.setattr(convert_object_type_mutation, "convert_and_validate_object_type", convert_after_another_write)

    new_id = await _convert_person(
        db=db,
        branch=default_branch,
        node_id=person.id,
        fields_mapping={"name": {"source_field": "name"}, "age": {"data": {"attribute_value": 30}}},
    )

    stored = await OwnershipRepository(db=db, branch=default_branch, at=None).read(node_ids=[new_id])
    assert stored[new_id].get(NODE_HOLDER).owner_ids == (group_ids[1],)


async def test_convert_object_type_gives_the_owners_of_a_write_that_commits_while_the_conversion_waits(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schemas_conversion: dict[str, Any],
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**schemas_conversion), branch=default_branch.name)
    default_branch.update_schema_hash()
    group_ids = []
    for name in ("dc-emea", "dc-security"):
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name=name)
        await group.save(db=db)
        group_ids.append(group.id)
    person = await Node.init(db=db, schema="TestconvPerson1")
    await person.new(db=db, name="owners-written-during-conversion")
    await person.save(db=db)
    await _write_owners(
        db=db,
        branch=default_branch,
        node_id=person.id,
        states={NODE_HOLDER: StoredOwnerState(owner_ids=(group_ids[0],))},
    )
    node = await NodeManager.get_one(db=db, branch=default_branch, id=person.id, raise_on_error=True)
    owners_are_written = asyncio.Event()

    async def write_owners() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            await _write_owners(
                db=dbt,
                branch=default_branch,
                node_id=person.id,
                states={NODE_HOLDER: StoredOwnerState(owner_ids=(group_ids[1],))},
            )
            owners_are_written.set()
            # The conversion starts while this transaction holds the node.
            await wait_for_the_other_write(db=db, other=conversion)

    async def convert() -> str:
        await asyncio.wait_for(owners_are_written.wait(), timeout=SECONDS_TO_WAIT)
        # The poll of the other write reads with the shared session, so the conversion needs its own.
        async with db.start_session() as session_db:
            new_node = await convert_and_validate_object_type(
                node=node,
                target_schema=registry.schema.get_node_schema(name="TestconvPerson2", branch=default_branch),
                mapping={
                    "name": ConversionFieldInput(source_field="name"),
                    "age": ConversionFieldInput(data=ConversionFieldValue(attribute_value=30)),
                },
                branch=default_branch,
                db=session_db,
            )
        return new_node.id

    conversion = asyncio.ensure_future(convert())
    _, new_id = await asyncio.gather(write_owners(), conversion)

    stored = await OwnershipRepository(db=db, branch=default_branch, at=None).read(node_ids=[new_id])
    assert stored[new_id].get(NODE_HOLDER).owner_ids == (group_ids[1],)


async def test_convert_object_type_keeps_the_owners_of_mapped_attributes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schemas_conversion: dict[str, Any],
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**schemas_conversion), branch=default_branch.name)
    default_branch.update_schema_hash()
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="dc-emea")
    await group.save(db=db)
    person = await Node.init(db=db, schema="TestconvPerson1")
    await person.new(db=db, name="with-attribute-owners", height=180, favorite_color="red")
    await person.save(db=db)
    owned = StoredOwnerState(owner_ids=(group.id,))
    await _write_owners(
        db=db,
        branch=default_branch,
        node_id=person.id,
        states={
            HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name"): owned,
            HolderKey(kind=HolderKind.ATTRIBUTE, attribute="height"): StoredOwnerState(owner_ids=()),
            HolderKey(kind=HolderKind.ATTRIBUTE, attribute="favorite_color"): owned,
        },
    )

    new_id = await _convert_person(
        db=db,
        branch=default_branch,
        node_id=person.id,
        fields_mapping={
            "name": {"source_field": "name"},
            "age": {"data": {"attribute_value": 30}},
            "favorite_color": {"data": {"attribute_value": "green"}},
        },
    )

    stored = await OwnershipRepository(db=db, branch=default_branch, at=None).read(node_ids=[new_id], attributes=True)
    assert {
        holder.attribute: state.owner_ids
        for holder, state in stored[new_id].holders.items()
        if holder.kind == HolderKind.ATTRIBUTE
    } == {"name": (group.id,), "height": ()}


async def test_convert_object_type_on_a_branch_keeps_the_owners_of_the_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schemas_conversion: dict[str, Any],
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**schemas_conversion), branch=default_branch.name)
    default_branch.update_schema_hash()
    group_ids: dict[str, str] = {}
    for name in ("dc-emea", "network-emea"):
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name=name)
        await group.save(db=db)
        group_ids[name] = group.id
    person = await Node.init(db=db, schema="TestconvPerson1")
    await person.new(db=db, name="branch-owners")
    await person.save(db=db)
    name_holder = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name")
    main_owners = StoredOwnerState(owner_ids=(group_ids["dc-emea"],))
    await _write_owners(
        db=db, branch=default_branch, node_id=person.id, states={NODE_HOLDER: main_owners, name_holder: main_owners}
    )
    branch = await create_branch(db=db, branch_name="conversion")
    branch_owners = StoredOwnerState(owner_ids=(group_ids["network-emea"],))
    await _write_owners(db=db, branch=branch, node_id=person.id, states={NODE_HOLDER: branch_owners})

    new_id = await _convert_person(
        db=db,
        branch=branch,
        node_id=person.id,
        fields_mapping={"name": {"source_field": "name"}, "age": {"data": {"attribute_value": 30}}},
    )

    on_branch = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[new_id], attributes=True)
    assert dict(on_branch[new_id].holders) == {NODE_HOLDER: branch_owners, name_holder: main_owners}
    on_default_branch = await OwnershipRepository(db=db, branch=default_branch, at=None).read(
        node_ids=[person.id], attributes=True
    )
    assert dict(on_default_branch[person.id].holders) == {NODE_HOLDER: main_owners, name_holder: main_owners}
    await verify_graph(db=db)


async def _field_owners(db: InfrahubDatabase, branch: Branch, node_id: str) -> dict[str | None, tuple[str, ...] | None]:
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id])
    return {
        holder.identifier: state.owner_ids
        for holder, state in stored[node_id].holders.items()
        if holder.kind == HolderKind.FIELD_SET
    }


@pytest.mark.parametrize(
    ("source_kind", "source_values", "source_field", "target_kind", "fields_mapping", "expected_identifiers"),
    [
        pytest.param(
            "TestconvPerson1",
            {},
            "favorite_car",
            "TestconvPerson2",
            {"age": {"data": {"attribute_value": 30}}, "worst_car": {"source_field": "favorite_car"}},
            {"person__favorite_car", "person__worst_car"},
            id="relationship-mapped-from-another-relationship",
        ),
        pytest.param(
            "TestconvPerson2", {"age": 30}, "worst_car", "TestconvPerson1", {}, set(), id="relationship-not-in-target"
        ),
    ],
)
async def test_convert_object_type_gives_the_owners_of_a_relationship_to_the_relationships_mapped_from_it(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schemas_conversion: dict[str, Any],
    source_kind: str,
    source_values: dict[str, Any],
    source_field: str,
    target_kind: str,
    fields_mapping: dict[str, Any],
    expected_identifiers: set[str],
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**schemas_conversion), branch=default_branch.name)
    default_branch.update_schema_hash()
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="dc-emea")
    await group.save(db=db)
    car = await Node.init(db=db, schema="TestconvCar")
    await car.new(db=db, name="car")
    await car.save(db=db)
    person = await Node.init(db=db, schema=source_kind)
    await person.new(db=db, name="with-relationship-owners", **source_values, **{source_field: car})
    await person.save(db=db)
    holder = field_holder(
        schema=registry.schema.get(name=source_kind, branch=default_branch, duplicate=False), field_name=source_field
    )
    assert holder is not None
    await OwnershipRepository(db=db, branch=default_branch, at=None).write(
        node_id=person.id,
        holder=holder,
        state=StoredOwnerState(owner_ids=(group.id,)),
        write_branch=default_branch,
        at=Timestamp(),
        user_id="test-user-id",
    )
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=CONVERT_OBJECT_TYPE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"node_id": person.id, "target_kind": target_kind, "fields_mapping": fields_mapping},
    )

    assert result.errors is None
    assert result.data
    new_id = result.data["ConvertObjectType"]["node"]["id"]
    assert await _field_owners(db=db, branch=default_branch, node_id=new_id) == dict.fromkeys(
        expected_identifiers, (group.id,)
    )


CONVERT_OBJECT_TYPE_MUTATION = """
mutation ConvertObjectType(
    $node_id: String!
    $target_kind: String!
    $fields_mapping: GenericScalar!
) {
    ConvertObjectType(data: {
        node_id: $node_id,
        target_kind: $target_kind,
        fields_mapping: $fields_mapping
    }) {
        ok
        node
    }
}
"""
