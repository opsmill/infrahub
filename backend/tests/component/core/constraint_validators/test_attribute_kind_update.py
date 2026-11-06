from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.attribute.kind import AttributeKindChecker, AttributeKindUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


async def test_query_success(db: InfrahubDatabase, default_branch: Branch, person_john_main: Node) -> None:
    car_schema = registry.schema.get(name="TestCar")
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="http://www.accord.com", nbr_seats=5, is_electric=False, owner=person_john_main.id)
    await car.save(db=db)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "URL"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    car_schema = registry.schema.get(name="TestCar")
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "IPNetwork"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="name",
            value=car_camry_main.name.value,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="name",
            value=car_accord_main.name.value,
        )
        in all_data_paths
    )


async def test_query_update_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    branch: Branch,
) -> None:
    car_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_accord.name.value = "http://www.accord.com"
    await car_accord.save(db=db)
    car_volt = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
    car_volt.name.value = "still-not-a-url.com"
    await car_volt.save(db=db)
    car_schema = registry.schema.get(name="TestCar", branch=branch)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "URL"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="name",
            value=car_camry_main.name.value,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_volt_main.id,
            kind="TestCar",
            field_name="name",
            value="still-not-a-url.com",
        )
        in all_data_paths
    )


async def test_query_update_on_branch_with_too_large_value(
    db: InfrahubDatabase,
    default_branch: Branch,
    all_attribute_types_schema: NodeSchema,
) -> None:
    main_node = await Node.init(db=db, schema=all_attribute_types_schema.kind, branch=default_branch)
    await main_node.new(db=db, name="number_one", mystring="abc", mytextarea="abcdef")
    await main_node.save(db=db)

    branch = await create_branch(db=db, branch_name="branch-too-large")

    branch_node = await NodeManager.get_one(db=db, branch=branch, id=main_node.id)
    branch_node.mytextarea.value = "abcdef" * 1000
    await branch_node.save(db=db)

    node_schema = registry.schema.get_node_schema(name=all_attribute_types_schema.kind, branch=branch)
    name_attr = node_schema.get_attribute(name="mytextarea")
    name_attr.kind = "Text"
    registry.schema.set(name=all_attribute_types_schema.kind, schema=node_schema, branch=default_branch.name)

    schema_path = SchemaPath(
        path_type=SchemaPathType.ATTRIBUTE, schema_kind=all_attribute_types_schema.kind, field_name="mytextarea"
    )

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert next(iter(all_data_paths)) == DataPath(
        branch=branch.name,
        path_type=PathType.ATTRIBUTE,
        node_id=main_node.id,
        kind=all_attribute_types_schema.kind,
        field_name="mytextarea",
        value="abcdef" * 1000,
    )


async def _get_kind_change_data_paths(
    db: InfrahubDatabase, branch: Branch, node_schema: NodeSchema, field_name: str, new_kind: str
) -> set[DataPath]:
    attr = node_schema.get_attribute(name=field_name)
    attr.kind = new_kind
    registry.schema.set(name=node_schema.kind, schema=node_schema, branch=branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=node_schema.kind, field_name=field_name)
    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )
    await query.execute(db=db)

    return set((await query.get_paths()).get_all_data_paths())


async def test_query_iphost_to_ipaddress_is_blocked(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    """An IPHost value carries a prefix, which is not a valid IPAddress, so the change is refused."""
    node = await Node.init(db=db, schema=all_attribute_types_schema.kind, branch=default_branch)
    await node.new(db=db, name="host", ipaddress="10.0.0.1/32")
    await node.save(db=db)

    all_data_paths = await _get_kind_change_data_paths(
        db=db,
        branch=default_branch,
        node_schema=all_attribute_types_schema,
        field_name="ipaddress",
        new_kind="IPAddress",
    )

    assert all_data_paths == {
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=node.id,
            kind=all_attribute_types_schema.kind,
            field_name="ipaddress",
            value="10.0.0.1/32",
        )
    }


async def test_query_ipaddress_to_iphost_is_blocked(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    """A bare address parses as an IPHost but is not canonical for it, and no migration rewrites it."""
    node = await Node.init(db=db, schema=all_attribute_types_schema.kind, branch=default_branch)
    await node.new(db=db, name="host", bare_address="10.0.0.1")
    await node.save(db=db)

    all_data_paths = await _get_kind_change_data_paths(
        db=db,
        branch=default_branch,
        node_schema=all_attribute_types_schema,
        field_name="bare_address",
        new_kind="IPHost",
    )

    assert all_data_paths == {
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=node.id,
            kind=all_attribute_types_schema.kind,
            field_name="bare_address",
            value="10.0.0.1",
        )
    }


async def test_query_iphost_to_ipnetwork_with_canonical_values_is_allowed(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    """A value already canonical for the new IP kind is left alone, the check is not block-everything."""
    node = await Node.init(db=db, schema=all_attribute_types_schema.kind, branch=default_branch)
    await node.new(db=db, name="net", ipaddress="10.0.0.0/24")
    await node.save(db=db)

    all_data_paths = await _get_kind_change_data_paths(
        db=db,
        branch=default_branch,
        node_schema=all_attribute_types_schema,
        field_name="ipaddress",
        new_kind="IPNetwork",
    )

    assert all_data_paths == set()


async def test_query_text_to_macaddress_with_non_canonical_value_is_blocked(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node
) -> None:
    """MacAddress normalizes too, so a dash-delimited value is refused rather than left un-rewritten."""
    car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    car.get_attribute("name").value = "aa-bb-cc-dd-ee-ff"
    await car.save(db=db)

    all_data_paths = await _get_kind_change_data_paths(
        db=db,
        branch=default_branch,
        node_schema=registry.schema.get_node_schema(name="TestCar", branch=default_branch),
        field_name="name",
        new_kind="MacAddress",
    )

    assert all_data_paths == {
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="name",
            value="aa-bb-cc-dd-ee-ff",
        )
    }


async def test_query_text_to_macaddress_with_canonical_value_is_allowed(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node
) -> None:
    """An already-canonical MacAddress passes, so the check does not block every conversion."""
    car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    car.get_attribute("name").value = "AA:BB:CC:DD:EE:FF"
    await car.save(db=db)

    all_data_paths = await _get_kind_change_data_paths(
        db=db,
        branch=default_branch,
        node_schema=registry.schema.get_node_schema(name="TestCar", branch=default_branch),
        field_name="name",
        new_kind="MacAddress",
    )

    assert all_data_paths == set()


async def test_query_update_on_branch_with_parameters_violation(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    branch: Branch,
) -> None:
    car_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_accord.name.value = "ACCORD"
    await car_accord.save(db=db)
    car_volt = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
    car_volt.name.value = "VOLT"
    await car_volt.save(db=db)
    car_schema = registry.schema.get(name="TestCar", branch=branch)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.parameters.regex = "^[a-z]+$"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="name",
            value=car_accord.name.value,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_volt_main.id,
            kind="TestCar",
            field_name="name",
            value=car_volt.name.value,
        )
        in all_data_paths
    )


async def test_query_delete_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    branch: Branch,
) -> None:
    car_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_accord.name.value = "1234"
    await car_accord.save(db=db)
    car_volt = await NodeManager.get_one(db=db, branch=branch, id=car_volt_main.id)
    await car_volt.delete(db=db)
    car_schema = registry.schema.get(name="TestCar", branch=branch)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "URL"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name")

    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="name",
            value=car_camry_main.name.value,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_accord_main.id,
            kind="TestCar",
            field_name="name",
            value="1234",
        )
        in all_data_paths
    )


async def test_validator(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_camry_main: Node,
    car_prius_main: Node,
    branch: Branch,
) -> None:
    car = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    car.name.value = "http://www.accord.com"
    await car.save(db=db)
    car2 = await NodeManager.get_one(id=car_camry_main.id, db=db, branch=branch)
    car2.name.value = "one-internet-please"
    await car2.save(db=db)

    car_schema = registry.schema.get(name="TestCar", branch=branch)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "URL"
    registry.schema.set(name="TestCar", schema=car_schema, branch=default_branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.kind.update",
        node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name"),
        schema_branch=SchemaBranch(cache={}, name="test"),
    )

    constraint_checker = AttributeKindChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=car_camry_main.id,
            kind="TestCar",
            field_name="name",
            value="one-internet-please",
        )
        in data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            node_id=car_prius_main.id,
            path_type=PathType.ATTRIBUTE,
            kind="TestCar",
            field_name="name",
            value=car_prius_main.name.value,
        )
        in data_paths
    )


async def test_list_attribute_regex_validation(
    db: InfrahubDatabase,
    default_branch: Branch,
    all_attribute_types_schema: NodeSchema,
):
    """Test that List attribute regex validation checks each item individually, not the serialized string."""
    # Create a node with a List attribute containing values that will become invalid
    node = await Node.init(db=db, schema=all_attribute_types_schema.kind, branch=default_branch)
    await node.new(db=db, name="test_node", mystring="test", mylist=["tcp:443", "telnet", "udp:53"])
    await node.save(db=db)

    # Update schema to add regex validation that makes "telnet" invalid
    node_schema = registry.schema.get_node_schema(name=all_attribute_types_schema.kind, branch=default_branch)
    list_attr = node_schema.get_attribute(name="mylist")
    list_attr.parameters.regex = r"^(tcp|udp):[\d-]+$"
    registry.schema.set(name=all_attribute_types_schema.kind, schema=node_schema, branch=default_branch.name)

    schema_path = SchemaPath(
        path_type=SchemaPathType.ATTRIBUTE, schema_kind=all_attribute_types_schema.kind, field_name="mylist"
    )

    # Run validation - should fail since "telnet" doesn't match the new regex
    query = await AttributeKindUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )
    await query.execute(db=db)
    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    # Value is stored as JSON string in database
    assert next(iter(all_data_paths)) == DataPath(
        branch=default_branch.name,
        path_type=PathType.ATTRIBUTE,
        node_id=node.id,
        kind=all_attribute_types_schema.kind,
        field_name="mylist",
        value='["tcp:443","telnet","udp:53"]',
    )
