from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import DropdownChoice, SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.attribute.choices import AttributeChoicesChecker
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


async def test_new_choice_value(db: InfrahubDatabase, default_branch: Branch, criticality_schema) -> None:
    crit_low = await Node.init(db=db, schema=criticality_schema)
    await crit_low.new(db=db, name="low", level=4, status="active")
    await crit_low.save(db=db)
    crit_med = await Node.init(db=db, schema=criticality_schema)
    await crit_med.new(db=db, name="med", level=4, status="passive")
    await crit_med.save(db=db)

    crit_schema = registry.schema.get(name="TestCriticality")
    status_attr = crit_schema.get_attribute(name="status")
    status_attr.choices.append(DropdownChoice(name="another-thing"))

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name="attribute.choices.update",
        node_schema=crit_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeChoicesChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    all_data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_remove_choice(db: InfrahubDatabase, default_branch: Branch, criticality_schema) -> None:
    crit_low = await Node.init(db=db, schema=criticality_schema)
    await crit_low.new(db=db, name="low", level=4, status="active")
    await crit_low.save(db=db)
    crit_med = await Node.init(db=db, schema=criticality_schema)
    await crit_med.new(db=db, name="med", level=4, status="passive")
    await crit_med.save(db=db)

    crit_schema = registry.schema.get(name="TestCriticality")
    status_attr = crit_schema.get_attribute(name="status")
    status_attr.choices = [DropdownChoice(name="active", color="#00ff00", description="Online things")]

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name="attribute.choices.update",
        node_schema=crit_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeChoicesChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    all_data_paths = grouped_data_paths[0].get_all_data_paths()
    assert all_data_paths == [
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_med.id,
            kind="TestCriticality",
            field_name="status",
            value="passive",
        )
    ]


async def test_convert_to_choice(db: InfrahubDatabase, branch: Branch, criticality_schema) -> None:
    crit_low = await Node.init(db=db, schema=criticality_schema, branch=branch)
    await crit_low.new(db=db, name="low", level=4, status="active")
    await crit_low.save(db=db)
    crit_med = await Node.init(db=db, schema=criticality_schema, branch=branch)
    await crit_med.new(db=db, name="med", level=4, status="passive")
    await crit_med.save(db=db)

    crit_schema = registry.schema.get(name="TestCriticality", branch=branch)
    name_attr = crit_schema.get_attribute(name="name")
    name_attr.choices = [DropdownChoice(name="nothing")]
    name_attr.kind = "Dropdown"

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.choices.update",
        node_schema=crit_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="name"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeChoicesChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    all_data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_med.id,
            kind="TestCriticality",
            field_name="name",
            value="med",
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_low.id,
            kind="TestCriticality",
            field_name="name",
            value="low",
        )
        in all_data_paths
    )


async def test_attribute_update_on_branch(
    db: InfrahubDatabase, branch: Branch, criticality_schema, criticality_low, criticality_medium
) -> None:
    criticality_low.status.value = "passive"
    await criticality_low.save(db=db)

    await branch.rebase(db=db)
    crit_low = await NodeManager.get_one(id=criticality_low.id, db=db, branch=branch)
    crit_low.status.value = "active"
    await crit_low.save(db=db)
    crit_med = await NodeManager.get_one(id=criticality_medium.id, db=db, branch=branch)
    crit_med.status.value = "passive"
    await crit_med.save(db=db)
    crit_high = await Node.init(db=db, schema=criticality_schema, branch=branch)
    await crit_high.new(db=db, name="high", level=4, status="passive")
    await crit_high.save(db=db)

    crit_schema = registry.schema.get(name="TestCriticality", branch=branch)
    status_attr = crit_schema.get_attribute(name="status")
    status_attr.choices = [DropdownChoice(name="active", color="#00ff00", description="Online things")]

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.choices.update",
        node_schema=crit_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeChoicesChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    all_data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_med.id,
            kind="TestCriticality",
            field_name="status",
            value="passive",
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_high.id,
            kind="TestCriticality",
            field_name="status",
            value="passive",
        )
        in all_data_paths
    )


async def test_node_delete_on_branch(
    db: InfrahubDatabase, branch: Branch, criticality_schema, criticality_low, criticality_medium
) -> None:
    criticality_low.status.value = "passive"
    await criticality_low.save(db=db)

    await branch.rebase(db=db)
    crit_low = await NodeManager.get_one(id=criticality_low.id, db=db, branch=branch)
    await crit_low.delete(db=db)
    crit_med = await NodeManager.get_one(id=criticality_medium.id, db=db, branch=branch)
    crit_med.status.value = "passive"
    await crit_med.save(db=db)
    crit_high = await Node.init(db=db, schema=criticality_schema, branch=branch)
    await crit_high.new(db=db, name="high", level=4, status="passive")
    await crit_high.save(db=db)

    crit_schema = registry.schema.get(name="TestCriticality", branch=branch)
    status_attr = crit_schema.get_attribute(name="status")
    status_attr.choices = [DropdownChoice(name="active", color="#00ff00", description="Online things")]

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.choices.update",
        node_schema=crit_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeChoicesChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    all_data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_med.id,
            kind="TestCriticality",
            field_name="status",
            value="passive",
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_high.id,
            kind="TestCriticality",
            field_name="status",
            value="passive",
        )
        in all_data_paths
    )


async def test_validator(
    db: InfrahubDatabase, branch: Branch, criticality_schema, criticality_low, criticality_medium
) -> None:
    await branch.rebase(db=db)
    crit_low = await NodeManager.get_one(id=criticality_low.id, db=db, branch=branch)
    crit_low.status.value = "active"
    await crit_low.save(db=db)
    crit_med = await NodeManager.get_one(id=criticality_medium.id, db=db, branch=branch)
    crit_med.status.value = "passive"
    await crit_med.save(db=db)
    crit_high = await Node.init(db=db, schema=criticality_schema, branch=branch)
    await crit_high.new(db=db, name="high", level=4, status="passive")
    await crit_high.save(db=db)

    crit_schema = registry.schema.get(name="TestCriticality", branch=branch)
    status_attr = crit_schema.get_attribute(name="status")
    status_attr.choices = [DropdownChoice(name="active", color="#00ff00", description="Online things")]

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.choices.update",
        node_schema=crit_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status"),
        schema_branch=SchemaBranch(cache={}),
    )

    constraint_checker = AttributeChoicesChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 2
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_med.id,
            kind="TestCriticality",
            field_name="status",
            value="passive",
        )
        in data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=crit_high.id,
            kind="TestCriticality",
            field_name="status",
            value="passive",
        )
        in data_paths
    )


async def test_validator_generic_and_node_have_different_choices(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema_root: SchemaRoot,
    criticality_low: Node,
    criticality_medium: Node,
    branch: Branch,
) -> None:
    # add different choices to the status attribute on the generic
    criticality_schema_root.generics[0].attributes.append(
        AttributeSchema(
            name="status",
            kind="Dropdown",
            optional=True,
            choices=[DropdownChoice(name="generic_active"), DropdownChoice(name="generic_passive")],
        )
    )
    # add another schema that inherits from the generic, but does not override the status attribute
    criticality_schema_root.nodes.append(
        NodeSchema(
            name="CriticalityTwo",
            namespace="Test",
            inherit_from=["TestGenericCriticality"],
        )
    )
    registry.schema.register_schema(schema=criticality_schema_root, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)

    # create TestCriticalityTwo nodes
    crit_two_status = await Node.init(db=db, schema="TestCriticalityTwo", branch=branch)
    await crit_two_status.new(db=db, status="generic_active")
    await crit_two_status.save(db=db)
    crit_two_no_status = await Node.init(db=db, schema="TestCriticalityTwo", branch=branch)
    await crit_two_no_status.new(db=db)
    await crit_two_no_status.save(db=db)

    # update TestCriticality nodes
    crit_low = await NodeManager.get_one(id=criticality_low.id, db=db, branch=branch)
    crit_low.status.value = None
    await crit_low.save(db=db)
    crit_med = await NodeManager.get_one(id=criticality_medium.id, db=db, branch=branch)
    crit_med.status.value = "passive"
    await crit_med.save(db=db)

    # verify that no errors are raised for TestGenericCriticality
    constraint_checker = AttributeChoicesChecker(db=db, branch=branch)

    generic_crit_schema = registry.schema.get(name="TestGenericCriticality", branch=branch)
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.choices.update",
        node_schema=generic_crit_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestGenericCriticality", field_name="status"
        ),
        schema_branch=schema_branch,
    )
    grouped_data_paths = await constraint_checker.check(request)
    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 0

    # verify that no errors are raised for TestCriticality
    node_crit_schema = registry.schema.get_node_schema(name="TestCriticality", branch=branch)
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.choices.update",
        node_schema=node_crit_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status"),
        schema_branch=schema_branch,
    )
    grouped_data_paths = await constraint_checker.check(request)
    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 0
