from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import DropdownChoice
from infrahub.core.validators.attribute.choices import AttributeChoicesChecker, AttributeChoicesUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


async def test_query_new_choice_value(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    crit_low = await Node.init(db=db, schema=criticality_schema)
    await crit_low.new(db=db, name="low", level=4, status="active")
    await crit_low.save(db=db)
    crit_med = await Node.init(db=db, schema=criticality_schema)
    await crit_med.new(db=db, name="med", level=4, status="passive")
    await crit_med.save(db=db)

    crit_schema = registry.schema.get(name="TestCriticality")
    status_attr = crit_schema.get_attribute(name="status")
    status_attr.choices.append(DropdownChoice(name="another-thing"))

    node_schema = crit_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status")

    query = await AttributeChoicesUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_remove_choice(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    crit_low = await Node.init(db=db, schema=criticality_schema)
    await crit_low.new(db=db, name="low", level=4, status="active")
    await crit_low.save(db=db)
    crit_med = await Node.init(db=db, schema=criticality_schema)
    await crit_med.new(db=db, name="med", level=4, status="passive")
    await crit_med.save(db=db)

    crit_schema = registry.schema.get(name="TestCriticality")
    status_attr = crit_schema.get_attribute(name="status")
    status_attr.choices = [DropdownChoice(name="active", color="#00ff00", description="Online things")]

    node_schema = crit_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status")

    query = await AttributeChoicesUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
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


async def test_query_convert_to_choice(db: InfrahubDatabase, branch: Branch, criticality_schema):
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

    node_schema = crit_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="name")

    query = await AttributeChoicesUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
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


async def test_query_attribute_update_on_branch(
    db: InfrahubDatabase, branch: Branch, criticality_schema, criticality_low, criticality_medium
):
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
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status")

    query = await AttributeChoicesUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=crit_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
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


async def test_query_node_delete_on_branch(
    db: InfrahubDatabase, branch: Branch, criticality_schema, criticality_low, criticality_medium
):
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
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCriticality", field_name="status")

    query = await AttributeChoicesUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=crit_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
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


async def test_validator(db: InfrahubDatabase, branch: Branch, criticality_schema, criticality_low, criticality_medium):
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
