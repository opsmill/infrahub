from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import MetadataOptions, RelationshipKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.graphql import graphql
from tests.helpers.schema import CAR_SCHEMA, DEVICE_SCHEMA


async def test_create_with_object_template(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch: Branch
) -> None:
    registry.schema.register_schema(schema=DEVICE_SCHEMA, branch=branch.name)
    branch.update_schema_hash()

    query = """
    mutation NewDevice($device_name: String!, $template_id: String!) {
      TestingDeviceCreate(data: {
        object_template: {id: $template_id}
        name: {value: $device_name}
      }) {
        ok
        object {
          id
        }
      }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Random non-existing ID for template
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr01", "template_id": "b1dd214b-befd-47ef-8af3-675fd28b1ea3"},
    )
    assert "Unable to find the object template in the database" in result.errors[0].message

    device_template: Node = await Node.init(schema=f"Template{TestKind.DEVICE}", db=db, branch=branch)
    await device_template.new(
        db=db, template_name="MX204 Router", manufacturer="Juniper", height=1, weight=0, airflow="Front to rear"
    )
    await device_template.save(db=db)

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr01", "template_id": device_template.id},
    )
    assert not result.errors

    device = await NodeManager.get_one(
        db=db,
        kind=TestKind.DEVICE,
        branch=branch,
        id=result.data[f"{TestKind.DEVICE}Create"]["object"]["id"],
        include_metadata=MetadataOptions.SOURCE,
    )
    assert device
    assert device.name.value == "th2.par.asbr01"
    # Validate object is linked to object template
    device_template_node = await device.object_template.get_peer(db=db)
    assert device_template_node.id == device_template.id
    # No interfaces as there are none on the object template
    device_interfaces = await device.interfaces.get_peers(db=db)
    assert not device_interfaces
    # verify attributes and metadata
    assert device.manufacturer.value == "Juniper"
    assert device.manufacturer.is_default is False
    assert device.manufacturer.source_id == device_template.id
    assert device.height.value == 1
    assert device.height.is_default is False
    assert device.height.source_id == device_template.id
    assert device.weight.value == 0
    assert device.weight.is_default is False
    assert device.weight.source_id == device_template.id
    assert device.airflow.value.value == "Front to rear"
    assert device.airflow.is_default is False
    assert device.airflow.source_id == device_template.id
    assert device.part_number.value is None
    assert device.part_number.is_default is True
    assert device.part_number.source_id is None

    # Create interfaces on object template
    if_names = ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]
    interface_templates_by_name: dict[str, Node] = {}
    for if_name in if_names:
        interface_template: Node = await Node.init(
            schema=f"Template{TestKind.PHYSICAL_INTERFACE}", db=db, branch=branch
        )
        await interface_template.new(
            db=db, template_name=f"MX204 {if_name}", device=device_template, name=if_name, phys_type="QSFP28 (100GE)"
        )
        await interface_template.save(db=db)
        interface_templates_by_name[if_name] = interface_template

    await device_template.interfaces.update(db=db, data=list(interface_templates_by_name.values()))
    await device_template.save(db=db)

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr02", "template_id": device_template.id},
    )
    assert not result.errors
    assert result.data

    device = await NodeManager.get_one(
        db=db, kind=TestKind.DEVICE, branch=branch, id=result.data[f"{TestKind.DEVICE}Create"]["object"]["id"]
    )
    assert device
    assert device.name.value == "th2.par.asbr02"
    # Validate object is linked to object template
    device_template_node = await device.object_template.get_peer(db=db)
    assert device_template_node.id == device_template.id
    # Validate that interfaces relationship has been populated according to object template
    interfaces = await NodeManager.query(
        db=db, branch=branch, schema=TestKind.PHYSICAL_INTERFACE, include_metadata=MetadataOptions.SOURCE
    )
    assert len(interfaces) == len(if_names)
    device_interfaces = await device.interfaces.get_peers(db=db)
    assert len(device_interfaces) == len(if_names)
    assert sorted([interface.name.value for interface in device_interfaces.values()]) == if_names
    # verify attributes and metadata on interfaces
    for interface in interfaces:
        assert interface.name.value in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]
        template_obj = interface_templates_by_name[interface.name.value]
        assert interface.name.is_default is False
        assert interface.name.source_id == template_obj.id
        assert interface.phys_type.value.value == "QSFP28 (100GE)"
        assert interface.phys_type.is_default is False
        assert interface.phys_type.source_id == template_obj.id
        assert interface.enabled.value is True
        assert interface.enabled.is_default is True
        assert interface.enabled.source_id is None

    # Add a SFP to each interface of the object template
    template_interfaces = await device_template.interfaces.get_peers(db=db)
    sfp_templates_by_interface_name: dict[str, Node] = {}
    for interface in template_interfaces.values():
        sfp_template: Node = await Node.init(schema=f"Template{TestKind.SFP}", db=db, branch=branch)
        await sfp_template.new(
            db=db,
            template_name=f"QSFP {interface.name.value}",
            interface=interface,
            phys_type="QSFP28 (100GE)",
            serial_number=f"QSFP-{interface.name.value}",
        )
        await sfp_template.save(db=db)
        sfp_templates_by_interface_name[interface.name.value] = sfp_template

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr03", "template_id": device_template.id},
    )
    assert not result.errors

    assert result.data
    device = await NodeManager.get_one(
        db=db, kind=TestKind.DEVICE, branch=branch, id=result.data[f"{TestKind.DEVICE}Create"]["object"]["id"]
    )
    assert device
    assert device.name.value == "th2.par.asbr03"
    # Validate object is linked to object template
    device_template_node = await device.object_template.get_peer(db=db)
    assert device_template_node.id == device_template.id
    # Validate that interfaces relationship has been populated according to object template
    device_interfaces = await device.interfaces.get_peers(db=db)
    assert len(device_interfaces) == len(if_names)
    assert sorted([interface.name.value for interface in device_interfaces.values()]) == if_names
    # Validate that one SFP is attached to each interface
    device_sfps = [await interface.sfp.get_peer(db=db) for interface in device_interfaces.values()]
    assert len(device_sfps) == len(if_names)
    sfp_interfaces = [await sfp.interface.get_peer(db=db) for sfp in device_sfps]
    assert sorted([interface.name.value for interface in sfp_interfaces]) == if_names
    # verify attributes and metadata on SFPs
    for sfp in device_sfps:
        interface_name = sfp.serial_number.value.split("-", 1)[1]
        template_obj = sfp_templates_by_interface_name[interface_name]
        assert sfp.phys_type.value.value == "QSFP28 (100GE)"
        assert sfp.phys_type.is_default is False
        assert sfp.phys_type.source_id == template_obj.id
        assert sfp.serial_number.value == f"QSFP-{interface_name}"
        assert sfp.serial_number.is_default is False
        assert sfp.serial_number.source_id == template_obj.id
        assert sfp.part_number.value is None
        assert sfp.part_number.is_default is True
        assert sfp.part_number.source_id is None


async def test_create_with_object_template_and_real_object(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch: Branch
) -> None:
    """Test that relationships on sub-templates will correctly link the created sub-object to an existing object on non-component relationships."""
    updated_car_schema = CAR_SCHEMA.duplicate()
    manufacturer_schema = updated_car_schema.get(name=TestKind.MANUFACTURER)
    manufacturer_schema.generate_template = True
    cars_rel = manufacturer_schema.get_relationship(name="cars")
    cars_rel.kind = RelationshipKind.COMPONENT
    person_schema = updated_car_schema.get(name=TestKind.PERSON)
    person_schema.generate_template = True
    car_schema = updated_car_schema.get(name=TestKind.CAR)
    car_schema.generate_template = True
    manufacturer_rel = car_schema.get_relationship(name="manufacturer")
    manufacturer_rel.kind = RelationshipKind.PARENT
    registry.schema.register_schema(schema=updated_car_schema, branch=branch.name)

    manufacturer_object = await Node.init(schema=TestKind.MANUFACTURER, db=db, branch=branch)
    await manufacturer_object.new(db=db, name="Hark Motors")
    await manufacturer_object.save(db=db)

    person_object = await Node.init(schema=TestKind.PERSON, db=db, branch=branch)
    await person_object.new(db=db, name="John", height=180)
    await person_object.save(db=db)

    car_object = await Node.init(schema=TestKind.CAR, db=db, branch=branch)
    await car_object.new(db=db, name="Accord", manufacturer=manufacturer_object, owner=person_object, color="blurple")
    await car_object.save(db=db)

    manufacturer_template: Node = await Node.init(schema=f"Template{TestKind.MANUFACTURER}", db=db, branch=branch)
    await manufacturer_template.new(db=db, template_name="m_template", customers=[person_object])
    await manufacturer_template.save(db=db)

    car_template_with_person_object = await Node.init(schema=f"Template{TestKind.CAR}", db=db, branch=branch)
    await car_template_with_person_object.new(
        db=db,
        template_name="c_template",
        name="Civic",
        color="blurple",
        manufacturer=manufacturer_template,
        owner=person_object,
    )
    await car_template_with_person_object.save(db=db)

    create_manufacturer_with_template_query = """
    mutation CreateManufacturerWithTemplate($manufacturer_name: String!, $template_id: String!) {
      TestingManufacturerCreate(data: {
        name: {value: $manufacturer_name}
        object_template: {id: $template_id}
      }) {
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
        source=create_manufacturer_with_template_query,
        context_value=gql_params.context,
        variable_values={"manufacturer_name": "Fresh Motors", "template_id": manufacturer_template.id},
    )
    assert not result.errors
    new_manufacturer = await NodeManager.get_one(
        db=db,
        kind=TestKind.MANUFACTURER,
        branch=branch,
        id=result.data[f"{TestKind.MANUFACTURER}Create"]["object"]["id"],
    )
    assert new_manufacturer
    assert new_manufacturer.name.value == "Fresh Motors"
    customers_peers = await new_manufacturer.customers.get_peers(db=db)
    assert len(customers_peers) == 1
    customers_by_name = {person.name.value: person for person in customers_peers.values()}
    # check non-template person
    non_template_person = customers_by_name["John"]
    assert non_template_person.id == person_object.id

    cars_peers = await new_manufacturer.cars.get_peers(db=db)
    assert len(cars_peers) == 1
    cars_by_name = {car.name.value: car for car in cars_peers.values()}
    # check car template with person object
    car_template_with_person_object = cars_by_name["Civic"]
    assert car_template_with_person_object.color.value == "blurple"
    car_manufacturer = await car_template_with_person_object.manufacturer.get_peer(db=db)
    assert car_manufacturer.id == new_manufacturer.id
    car_owner = await car_template_with_person_object.owner.get_peer(db=db)
    assert car_owner.id == person_object.id


async def test_create_without_object_template(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch: Branch
) -> None:
    registry.schema.register_schema(schema=DEVICE_SCHEMA, branch=branch.name)
    branch.update_schema_hash()

    query = """
    mutation NewDevice($device_name: String!, $manufacturer: String!) {
      TestingDeviceCreate(data: {
        name: {value: $device_name}
        manufacturer: {value: $manufacturer}
        height: {value: 1}
        weight: {value: 6}
        airflow: {value: "Front to rear"}
      }) {
        ok
        object {
          id
        }
      }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr01", "manufacturer": "Juniper"},
    )
    assert not result.errors

    device = await NodeManager.get_one(
        db=db, kind=TestKind.DEVICE, branch=branch, id=result.data[f"{TestKind.DEVICE}Create"]["object"]["id"]
    )
    assert device
    assert device.name.value == "th2.par.asbr01"
    # Validate object not is linked to object template
    device_template_node = await device.object_template.get_peer(db=db)
    assert not device_template_node


async def test_create_sub_object_template_by_hfid(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch: Branch
) -> None:
    registry.schema.register_schema(schema=DEVICE_SCHEMA, branch=branch.name)
    branch.update_schema_hash()

    device_template = await Node.init(db=db, schema=f"Template{TestKind.DEVICE}", branch=branch)
    await device_template.new(
        db=db, template_name="MX204 Router", manufacturer="Juniper", height=1, weight=6, airflow="Front to rear"
    )
    await device_template.save(db=db)
    device_template_hfid = await device_template.get_hfid(db=db)

    template = await registry.manager.get_one_by_hfid(
        db=db, branch=branch, kind=f"Template{TestKind.INTERFACE_HOLDER}", hfid=device_template_hfid
    )
    assert device_template.id == template.id

    query = """
    mutation CreateTemplateInterfaceWithHFID($template_name: String!, $device_template_hfid: [String!], $name: String!, $phys_type: String!) {
      TemplateTestingPhysicalInterfaceCreate(
        data:{
          template_name: {value: $template_name}
          device: {hfid: $device_template_hfid}
          name: {value: $name}
          phys_type: {value: $phys_type}
        }
      ) {
        ok
        object {
          id
        }
      }
    }
    """

    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "template_name": "MX204 et-0/0/0",
            "device_template_hfid": device_template_hfid,
            "name": "et-0/0/0",
            "phys_type": "QSFP28 (100GE)",
        },
    )
    assert not result.errors

    node_id = result.data["TemplateTestingPhysicalInterfaceCreate"]["object"]["id"]
    assert node_id

    interface_template = await registry.manager.get_one(db=db, branch=branch, id=node_id)
    assert interface_template
    assert (await interface_template.device.get_peer(db=db)).id == device_template.id
