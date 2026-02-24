from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.events.node_action import NodeMutatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.constants import TestKind
from tests.helpers.graphql import graphql
from tests.helpers.schema import COLOR, TICKET, TSHIRT
from tests.node_creation import create_and_save


async def test_upsert_existing_simple_object_by_id(
    db: InfrahubDatabase, person_john_main: Node, branch: Branch
) -> None:
    query = (
        """
    mutation {
        TestPersonUpsert(data: {id: "%s", name: { value: "Jim"}}) {
            ok
        }
    }
    """
        % person_john_main.id
    )
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestPersonUpsert"]["ok"] is True

    obj1 = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    assert obj1.name.value == "Jim"
    assert obj1.height.value == 180


async def test_upsert_existing_simple_object_by_default_filter(
    db: InfrahubDatabase, person_schema_default_filter, default_branch
) -> None:
    registry.schema.register_schema(schema=person_schema_default_filter)

    person = await Node.init(db=db, schema="TestPersonDF")
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    query = """
    mutation {
        TestPersonDFUpsert(data: {name: { value: "John"}, height: {value: 138}}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestPersonDFUpsert"]["ok"] is True
    assert result.data["TestPersonDFUpsert"]["object"]["id"] == person.id

    obj1 = await NodeManager.get_one(db=db, id=person.id)
    assert obj1.name.value == "John"
    assert obj1.height.value == 138


async def test_upsert_event_on_no_change(
    db: InfrahubDatabase,
    car_person_schema: Node,
    branch: Branch,
    session_first_account: AccountSession,
) -> None:
    query = """
    mutation {
        TestPersonUpsert(data: {name: { value: "Howard"}, height: {value: 174}}) {
            ok
            object {
                id
            }
        }
    }
    """
    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestPersonUpsert"]["ok"] is True
    howard_id = result.data["TestPersonUpsert"]["object"]["id"]

    obj1 = await NodeManager.get_one(db=db, id=howard_id, branch=branch)
    assert obj1.name.value == "Howard"
    assert obj1.height.value == 174

    assert gql_params.context.background
    await gql_params.context.background()
    assert len(memory_event.events) == 1
    event = memory_event.events[0]
    assert isinstance(event, NodeMutatedEvent)
    assert sorted(event.changelog.attributes.keys()) == ["display_label", "height", "human_friendly_id", "name"]

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=branch, service=service, account_session=session_first_account
    )
    result_second_time = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result_second_time.errors is None
    assert result_second_time.data
    assert result_second_time.data["TestPersonUpsert"]["ok"] is True

    assert gql_params.context.background
    await gql_params.context.background()
    assert len(memory_event.events) == 0


async def test_upsert_create_simple_object_no_id(db: InfrahubDatabase, person_john_main, branch: Branch) -> None:
    query = """
    mutation {
        TestPersonUpsert(data: {name: { value: "%s"}, height: {value: %s}}) {
            ok
            object {
                id
            }
        }
    }
    """ % ("Ellen Ripley", 179)

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestPersonUpsert"]["ok"] is True

    person_id = result.data["TestPersonUpsert"]["object"]["id"]
    obj1 = await NodeManager.get_one(db=db, id=person_id, branch=branch)
    assert obj1.name.value == "Ellen Ripley"
    assert obj1.height.value == 179


async def test_id_for_other_schema_raises_error(
    db: InfrahubDatabase, person_john_main, car_accord_main, branch: Branch
) -> None:
    query = (
        """
    mutation {
        TestPersonUpsert(data: {id: "%s", name: {value: "John"}, height: { value: 182}}) {
            ok
        }
    }
    """
        % car_accord_main.id
    )
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    expected_error = f"Node with id {car_accord_main.id} exists, but it is a TestCar, not TestPerson"
    assert result.errors
    assert any(expected_error in error.message for error in result.errors)


async def test_update_by_id_to_nonunique_value_raises_error(
    db: InfrahubDatabase, person_john_main, person_jim_main, branch: Branch
) -> None:
    query = (
        """
    mutation {
        TestPersonUpsert(data: {id: "%s", name: {value: "Jim"}}) {
            ok
        }
    }
    """
        % person_john_main.id
    )
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    expected_error = "Violates uniqueness constraint 'name'"
    assert result.errors
    assert any(expected_error in error.message for error in result.errors)


async def test_non_unique_value_raises_error(
    db: InfrahubDatabase, person_schema_unique_attr_non_hfid, branch: Branch
) -> None:
    _ = await create_and_save(db=db, schema="TestPerson", name="Jack", bag="bag-jacks")

    # Make sure correct raised error is raised while violating uniqueness constraint of a non hfid-related attribute.
    query = """
    mutation {
        TestPersonUpsert(data: {name: {value: "Jim"}, bag: {value: "bag-jacks"}}) {
            ok
        }
    }
    """

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint 'bag'" in result.errors[0].message


async def test_upsert_existing_with_enough_information_for_hfid(
    db: InfrahubDatabase, person_schema_unique_attr_non_hfid, default_branch: Branch
) -> None:
    car_name = "Ferramboghinierati"
    car_color_1 = "blue"
    car_color_2 = "red"
    fred = await create_and_save(db=db, schema="TestPerson", name="Fred", bag="bag-fred", branch=default_branch)
    car = await create_and_save(
        db=db, schema="TestCar", name=car_name, owner=fred, color=car_color_1, branch=default_branch
    )
    other_car = await create_and_save(
        db=db, schema="TestCar", name="pinto", owner=fred, color="brown", branch=default_branch
    )
    thing1 = await create_and_save(db=db, schema="TestThing", value="thing1", branch=default_branch)
    thing2 = await create_and_save(db=db, schema="TestThing", value="thing2", car=other_car, branch=default_branch)

    # upsert the existing car with new attr and relationship data
    query = """
    mutation($car_name: String!, $owner_id: String!, $color: String!) {
        TestCarUpsert(
            data: {
                name: {value: $car_name},
                owner: {id: $owner_id},
                color: {value: $color},
                things: [
                    {id: "%(id1)s"}
                ]
            }
        ) {
            ok
            object {
                id
                name {value}
                color {value}
                owner {node {id}}
            }
        }
    }
    """ % {"id1": thing1.id}
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"car_name": car_name, "owner_id": fred.id, "color": car_color_2},
    )
    assert result.errors is None

    # illegal upsert that would add two peers on a TestThing.car relationship
    query = """
    mutation($car_name: String!, $owner_id: String!, $color: String!) {
        TestCarUpsert(
            data: {
                name: {value: $car_name},
                owner: {id: $owner_id},
                color: {value: $color},
                things: [
                    {id: "%(id1)s"}, {id: "%(id2)s"}
                ]
            }
        ) {
            ok
            object {
                id
                name {value}
                color {value}
                owner {node {id}}
            }
        }
    }
    """ % {"id1": thing1.id, "id2": thing2.id}
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"car_name": car_name, "owner_id": fred.id, "color": car_color_2},
    )
    assert result.errors
    assert result.errors[0].message == f"Node {thing2.id} has 2 peers for carthings, maximum of 1 allowed"

    # delete the TestThing.car relationship and try again
    await thing2.car.update(db=db, data=[None])
    await thing2.save(db=db)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"car_name": car_name, "owner_id": fred.id, "color": car_color_2},
    )
    assert not result.errors
    assert result.data
    assert result.data["TestCarUpsert"]["object"]["id"] == car.id
    assert result.data["TestCarUpsert"]["object"]["color"]["value"] == car_color_2
    assert result.data["TestCarUpsert"]["object"]["owner"]["node"]["id"] == fred.id

    # validate upsert succeeded and all data is as expected
    all_cars = await NodeManager.query(db=db, branch=default_branch, schema="TestCar")
    assert len(all_cars) == 2
    assert {one_car.id for one_car in all_cars} == {car.id, other_car.id}
    retrieved_car = await NodeManager.get_one(db=db, branch=default_branch, id=car.id, prefetch_relationships=True)
    assert retrieved_car.name.value == car_name
    assert retrieved_car.color.value == car_color_2
    assert (await retrieved_car.owner.get_peer(db=db)).id == fred.id
    thing_peers = await retrieved_car.things.get_peers(db=db)
    assert set(thing_peers.keys()) == {thing1.id, thing2.id}


async def test_upsert_existing_hfid_with_non_hfid_unique_attr(
    db: InfrahubDatabase, person_schema_unique_attr_non_hfid, branch: Branch
) -> None:
    _ = await create_and_save(db=db, schema="TestPerson", name="Fred", bag="bag-fred", branch=branch)

    query = """
    mutation {
        TestPersonUpsert(data: {name: {value: "Fred"}, bag: {value: "bag-fred"}}) {
            ok
        }
    }
    """
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None


async def test_with_hfid_existing(db: InfrahubDatabase, default_branch, animal_person_schema) -> None:
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    query = (
        """
    mutation {
        TestDogUpsert(data: {
            hfid: ["Jack", "Rocky"],
            name: { value: "Bella" },
            breed: { value: "Labrador" },
            color: { value: "black" },
            owner: { id: "%s" }
        }) {
            ok
            object {
                id
                color {
                    value
                }
            }
        }
    }
    """
        % person1.id
    )
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data
    assert result.data["TestDogUpsert"]["ok"] is True
    assert result.data["TestDogUpsert"]["object"] == {"color": {"value": "black"}, "id": dog1.id}


async def test_with_hfid_new(db: InfrahubDatabase, default_branch, animal_person_schema) -> None:
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    query = (
        """
    mutation {
        TestDogUpsert(data: {
            hfid: ["Jack", "Bella"],
            name: { value: "Bella" },
            breed: { value: "Labrador" },
            color: { value: "black" },
            owner: { id: "%s" }
        }) {
            ok
            object {
                id
                name {
                    value
                }
                color {
                    value
                }
                breed {
                    value
                }
            }
        }
    }
    """
        % person1.id
    )

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data
    assert result.data["TestDogUpsert"]["ok"] is True
    new_id = result.data["TestDogUpsert"]["object"]["id"]
    assert result.data["TestDogUpsert"]["object"] == {
        "breed": {"value": "Labrador"},
        "color": {"value": "black"},
        "id": new_id,
        "name": {"value": "Bella"},
    }


async def test_with_constructed_hfid(db: InfrahubDatabase, default_branch, animal_person_schema) -> None:
    """Validate that we can construct an HFID out of the payload without specifying all parts."""

    person_schema = animal_person_schema.get(name="TestPerson")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="John Snow")
    await person1.save(db=db)

    query = """
    mutation UpsertWolf($owner: String!, $weight: BigInt!) {
        TestDogUpsert(data: {
            name: { value: "Ghost" },
            breed: { value: "Direwolf" },
            color: { value: "White" },
            owner: { id: $owner },
            weight: { value: $weight }
        }) {
            ok
            object {
                id
                name {
                    value
                }
                color {
                    value
                }
                breed {
                    value
                }
                weight {
                    value
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    # Create initial node
    initial_weight = 14
    create_result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"owner": "John Snow", "weight": initial_weight},
    )

    # Update previously created node
    updated_weight = 68
    update_result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"owner": "John Snow", "weight": updated_weight},
    )

    assert create_result.errors is None
    assert create_result.data
    assert create_result.data["TestDogUpsert"]["ok"] is True
    ghost_id = create_result.data["TestDogUpsert"]["object"]["id"]
    assert create_result.data["TestDogUpsert"]["object"] == {
        "breed": {"value": "Direwolf"},
        "color": {"value": "White"},
        "id": ghost_id,
        "name": {"value": "Ghost"},
        "weight": {"value": initial_weight},
    }

    assert update_result.errors is None
    assert update_result.data
    assert update_result.data["TestDogUpsert"]["ok"] is True
    assert ghost_id == update_result.data["TestDogUpsert"]["object"]["id"]
    assert update_result.data["TestDogUpsert"]["object"] == {
        "breed": {"value": "Direwolf"},
        "color": {"value": "White"},
        "id": ghost_id,
        "name": {"value": "Ghost"},
        "weight": {"value": updated_weight},
    }


async def test_with_constructed_hfid_with_numbers(
    db: InfrahubDatabase, default_branch: Branch, data_schema: None
) -> None:
    """Validate that we can construct an HFID out of the payload without specifying all parts."""

    registry.schema.register_schema(schema=SchemaRoot(nodes=[TICKET]), branch=default_branch.name)

    first_ticket = await Node.init(schema=TestKind.TICKET, db=db)
    await first_ticket.new(db=db, title="first", ticket_id=1, description="Add more info")
    await first_ticket.save(db=db)

    query = """
    mutation UpsertTicket {
        TestingTicketUpsert(data: {
            title: { value: "first" },
            ticket_id: { value: 1 },
            description: { value: "Here is the update" },
        }) {
            ok
            object {
                id
                title {
                    value
                }
                description {
                    value
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    update_result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
    )

    assert update_result.errors is None
    assert update_result.data
    assert update_result.data["TestingTicketUpsert"]["ok"] is True
    assert update_result.data["TestingTicketUpsert"]["object"] == {
        "title": {"value": "first"},
        "description": {"value": "Here is the update"},
        "id": first_ticket.id,
    }


async def test_upsert_node_on_branch_with_hfid_on_default(
    db: InfrahubDatabase, default_branch, car_person_schema
) -> None:
    # create a node on the default branch after the branch is created
    branch = await create_branch(branch_name="test-branch", db=db)
    person = await create_and_save(db=db, branch=default_branch, schema="TestPerson", name="John", height=182)

    # try to upsert a node on the branch with a matching hfid
    query = """
    mutation {
        TestPersonUpsert(data: {name: { value: "John"}, height: {value: 183}}) {
            ok
            object {
                id
            }
        }
    }
    """
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert (
        f"Node {person.id} / TestPerson uses this human-friendly ID, but does not exist on this branch"
        in result.errors[0].message
    )
    assert f"Please rebase this branch to access {person.id} / TestPerson" in result.errors[0].message


async def test_upsert_with_required_relationship_from_template(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """Validate that we can use a template to populate required relationships in upsert mutations.

    Steps:
      - Create a color node and a Tshirt template node.
      - Try to upsert a Tshirt without specifying color or template (should fail).
      - Upsert a Tshirt specifying the template (should succeed and apply the color from the template).
    """
    registry.schema.register_schema(schema=SchemaRoot(nodes=[TSHIRT, COLOR]), branch=default_branch.name)

    # Create a color node
    color_node = await Node.init(db=db, schema="TestingColor", branch=default_branch)
    await color_node.new(db=db, name="Red", description="Bright Red Color")
    await color_node.save(db=db)

    # Create a Tshirt template node with the color relationship set
    template_node = await Node.init(db=db, schema="TemplateTestingTShirt", branch=default_branch)
    await template_node.new(db=db, template_name="Basic Red Tshirt", color=color_node)
    await template_node.save(db=db)

    # Try to upsert a TShirt without specifying color or template (should fail)
    query_missing_required = """
    mutation {
        TestingTShirtUpsert(data: {name: {value: "My Shirt"} }) {
            ok
            object {
                id
                name { value }
                color { node { id name { value } } }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result_missing = await graphql(
        schema=gql_params.schema,
        source=query_missing_required,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result_missing.errors
    assert "color is mandatory for TestingTShirt at color" in str(result_missing.errors)

    # Upsert a Tshirt specifying the template (should succeed and apply the color from the template)
    query_with_template = """
    mutation UpsertTShirt($template_id: String!) {
        TestingTShirtUpsert(data: {
            name: {value: "My Tshirt"},
            object_template: {id: $template_id}
        }) {
            ok
            object {
                id
                name { value }
                color { node { id name { value } } }
            }
        }
    }
    """

    result_with_template = await graphql(
        schema=gql_params.schema,
        source=query_with_template,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"template_id": template_node.id},
    )
    assert result_with_template.errors is None
    assert result_with_template.data
    assert result_with_template.data["TestingTShirtUpsert"]["ok"] is True
    tshirt_obj = result_with_template.data["TestingTShirtUpsert"]["object"]
    assert tshirt_obj["name"]["value"] == "My Tshirt"
    assert tshirt_obj["color"]["node"]["id"] == color_node.id
    assert tshirt_obj["color"]["node"]["name"]["value"] == "Red"
