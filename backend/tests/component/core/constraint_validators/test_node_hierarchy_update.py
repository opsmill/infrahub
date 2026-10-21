import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.node.hierarchy import NodeHierarchyChecker, NodeHierarchyUpdateValidatorQuery
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def hierarchical_location_data_simple_and_small(
    db: InfrahubDatabase, hierarchical_location_schema_simple: SchemaRoot
) -> dict[str, Node]:
    nodes = {}

    r1 = await Node.init(db=db, schema="LocationRegion")
    await r1.new(db=db, name="r1")
    await r1.save(db=db)
    nodes[r1.name.value] = r1
    r2 = await Node.init(db=db, schema="LocationRegion")
    await r2.new(db=db, name="r2")
    await r2.save(db=db)
    nodes[r2.name.value] = r2
    s1r1 = await Node.init(db=db, schema="LocationSite")
    await s1r1.new(db=db, name="s1r1", parent=r1)
    await s1r1.save(db=db)
    nodes[s1r1.name.value] = s1r1
    s1r1_rack = await Node.init(db=db, schema="LocationRack")
    await s1r1_rack.new(db=db, name="s1r1_rack", parent=s1r1, status="online")
    await s1r1_rack.save(db=db)
    nodes[s1r1_rack.name.value] = s1r1_rack
    s2r1 = await Node.init(db=db, schema="LocationSite")
    await s2r1.new(db=db, name="s2r1", parent=r1)
    await s2r1.save(db=db)
    nodes[s2r1.name.value] = s2r1
    s2r1_rack = await Node.init(db=db, schema="LocationRack")
    await s2r1_rack.new(db=db, name="s2r1_rack", parent=s2r1, status="online")
    await s2r1_rack.save(db=db)
    nodes[s2r1_rack.name.value] = s2r1_rack
    s1r2 = await Node.init(db=db, schema="LocationSite")
    await s1r2.new(db=db, name="s1r2", parent=r2)
    await s1r2.save(db=db)
    nodes[s1r2.name.value] = s1r2
    s1r2_rack = await Node.init(db=db, schema="LocationRack")
    await s1r2_rack.new(db=db, name="s1r2_rack", parent=s1r2, status="online")
    await s1r2_rack.save(db=db)
    nodes[s1r2_rack.name.value] = s1r2_rack
    s2r2 = await Node.init(db=db, schema="LocationSite")
    await s2r2.new(db=db, name="s2r2", parent=r2)
    await s2r2.save(db=db)
    nodes[s2r2.name.value] = s2r2
    s2r2_rack = await Node.init(db=db, schema="LocationRack")
    await s2r2_rack.new(db=db, name="s2r2_rack", parent=s2r2, status="online")
    await s2r2_rack.save(db=db)
    nodes[s2r2_rack.name.value] = s2r2_rack

    return nodes


async def test_query_children_success(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple: dict[str, Node]
) -> None:
    site_schema = registry.schema.get(name="LocationSite")
    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="children")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db,
        branch=default_branch,
        node_schema=site_schema,
        schema_path=schema_path,
        check_children=True,
        allowed_peer_kinds=["LocationRack"],
        allowed_hierarchy_kinds=["LocationGeneric"],
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_parent_success(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple: dict[str, Node]
) -> None:
    site_schema = registry.schema.get(name="LocationSite")
    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="parent")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db,
        branch=default_branch,
        node_schema=site_schema,
        schema_path=schema_path,
        check_parent=True,
        allowed_peer_kinds=["LocationRegion"],
        allowed_hierarchy_kinds=["LocationGeneric"],
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_children_failure(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple_and_small: dict[str, Node]
) -> None:
    hldsas = hierarchical_location_data_simple_and_small
    site_schema = registry.schema.get(name="LocationSite")
    site_schema.children = "LocationRegion"

    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="children")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db,
        branch=default_branch,
        node_schema=site_schema,
        schema_path=schema_path,
        check_children=True,
        allowed_peer_kinds=["LocationRegion"],
        allowed_hierarchy_kinds=["LocationGeneric"],
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 4
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s1r1"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s1r1_rack"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s2r2"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s2r2_rack"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s1r2"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s1r2_rack"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s2r1"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s2r1_rack"].id,
        )
        in all_data_paths
    )


async def test_query_parent_failure(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple_and_small: dict[str, Node]
) -> None:
    hldsas = hierarchical_location_data_simple_and_small
    site_schema = registry.schema.get(name="LocationSite")
    site_schema.parent = "LocationRack"

    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="parent")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db,
        branch=default_branch,
        node_schema=site_schema,
        schema_path=schema_path,
        check_parent=True,
        allowed_peer_kinds=["LocationRack"],
        allowed_hierarchy_kinds=["LocationGeneric"],
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 4
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s1r1"].id,
            kind="LocationSite",
            field_name="parent",
            peer_id=hldsas["r1"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s2r2"].id,
            kind="LocationSite",
            field_name="parent",
            peer_id=hldsas["r2"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s1r2"].id,
            kind="LocationSite",
            field_name="parent",
            peer_id=hldsas["r2"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s2r1"].id,
            kind="LocationSite",
            field_name="parent",
            peer_id=hldsas["r1"].id,
        )
        in all_data_paths
    )


async def test_query_update_on_branch_failure(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    hierarchical_location_data_simple_and_small: dict[str, Node],
) -> None:
    hldsas = hierarchical_location_data_simple_and_small
    site_schema = registry.schema.get(name="LocationSite")
    site_schema.children = "LocationRegion"

    s1r1_rack2 = await Node.init(db=db, schema="LocationRack", branch=branch)
    await s1r1_rack2.new(db=db, name="s1r1_rack2", parent=hldsas["s1r1"], status="online")
    await s1r1_rack2.save(db=db)

    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="children")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db,
        branch=branch,
        node_schema=site_schema,
        schema_path=schema_path,
        check_children=True,
        allowed_peer_kinds=["LocationRegion"],
        allowed_hierarchy_kinds=["LocationGeneric"],
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 5
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s1r1"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s1r1_rack"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s1r1"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=s1r1_rack2.id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s2r2"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s2r2_rack"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s1r2"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s1r2_rack"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s2r1"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s2r1_rack"].id,
        )
        in all_data_paths
    )


async def test_query_delete_on_branch_failure(
    db: InfrahubDatabase,
    branch: Branch,
    default_branch: Branch,
    hierarchical_location_data_simple_and_small: dict[str, Node],
) -> None:
    hldsas = hierarchical_location_data_simple_and_small
    site_schema = registry.schema.get(name="LocationSite")
    site_schema.children = "LocationRegion"

    await branch.rebase(db=db)
    s1r1_rack1 = await NodeManager.get_one(db=db, id=hldsas["s1r1"].id, branch=branch)
    await s1r1_rack1.delete(db=db)

    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="children")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db,
        branch=branch,
        node_schema=site_schema,
        schema_path=schema_path,
        check_children=True,
        allowed_peer_kinds=["LocationRegion"],
        allowed_hierarchy_kinds=["LocationGeneric"],
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 3
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s2r2"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s2r2_rack"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s1r2"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s1r2_rack"].id,
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.NODE,
            node_id=hldsas["s2r1"].id,
            kind="LocationSite",
            field_name="children",
            peer_id=hldsas["s2r1_rack"].id,
        )
        in all_data_paths
    )


async def test_validator_parents_failure(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple_and_small: dict[str, Node]
) -> None:
    hldsas = hierarchical_location_data_simple_and_small
    site_schema = registry.schema.get(name="LocationSite")
    site_schema.parent = "LocationRack"

    registry.schema.set(name="LocationSite", schema=site_schema, branch=default_branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name="node.parent.update",
        node_schema=site_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="parent"),
        schema_branch=registry.schema.get_schema_branch(name=default_branch.name),
    )

    constraint_checker = NodeHierarchyChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 4
    assert {(dp.node_id, dp.peer_id) for dp in data_paths} == {
        (hldsas["s1r1"].id, hldsas["r1"].id),
        (hldsas["s2r1"].id, hldsas["r1"].id),
        (hldsas["s1r2"].id, hldsas["r2"].id),
        (hldsas["s2r2"].id, hldsas["r2"].id),
    }


async def test_validator_parents_success(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple_and_small: dict[str, Node]
) -> None:
    site_schema = registry.schema.get(name="LocationSite")

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name="node.parent.update",
        node_schema=site_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="parent"),
        schema_branch=registry.schema.get_schema_branch(name=default_branch.name),
    )

    constraint_checker = NodeHierarchyChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 0


async def test_validator_children_failure(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple_and_small: dict[str, Node]
) -> None:
    hldsas = hierarchical_location_data_simple_and_small
    site_schema = registry.schema.get(name="LocationSite")
    site_schema.children = "LocationRegion"

    registry.schema.set(name="LocationSite", schema=site_schema, branch=default_branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name="node.children.update",
        node_schema=site_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="children"),
        schema_branch=registry.schema.get_schema_branch(name=default_branch.name),
    )

    constraint_checker = NodeHierarchyChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 4
    assert {(dp.node_id, dp.peer_id) for dp in data_paths} == {
        (hldsas["s1r1"].id, hldsas["s1r1_rack"].id),
        (hldsas["s2r1"].id, hldsas["s2r1_rack"].id),
        (hldsas["s1r2"].id, hldsas["s1r2_rack"].id),
        (hldsas["s2r2"].id, hldsas["s2r2_rack"].id),
    }


async def test_validator_children_success(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple_and_small: dict[str, Node]
) -> None:
    site_schema = registry.schema.get(name="LocationSite")

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name="node.children.update",
        node_schema=site_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="children"),
        schema_branch=registry.schema.get_schema_branch(name=default_branch.name),
    )

    constraint_checker = NodeHierarchyChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 0


REGION_SCHEMA_ID = "region-schema-id"
RACK_SCHEMA_ID = "rack-schema-id"


def _rename_kind(schema_branch: SchemaBranch, kind: str, name: str) -> str:
    """Rename a kind in the schema branch and keep its schema id, as a schema load that renames a kind does."""
    schema = schema_branch.get_node(name=kind)
    schema.name = name
    schema_branch.delete(name=kind)
    schema_branch.set(name=schema.kind, schema=schema)
    return schema.kind


def _set_schema_id(schema_branch: SchemaBranch, kind: str, schema_id: str) -> None:
    schema = schema_branch.get_node(name=kind)
    schema.id = schema_id
    schema_branch.set(name=kind, schema=schema)


class TestHierarchyValidatorRenamedParent:
    """Checks against one dataset built once for the class.

    Stored sites keep the label of their renamed parent kind until its migration runs, so a rename must not be
    refused. Only a copy of main's schema, or the schema of a branch the test creates, is changed.
    """

    @pytest.fixture(scope="class")
    async def region_schema_with_id(
        self, default_branch_scope_class: Branch, hierarchical_location_data_simple_scope_class: dict[str, Node]
    ) -> None:
        current_schema = registry.schema.get_schema_branch(name=default_branch_scope_class.name)
        _set_schema_id(schema_branch=current_schema, kind="LocationRegion", schema_id=REGION_SCHEMA_ID)
        _set_schema_id(schema_branch=current_schema, kind="LocationRack", schema_id=RACK_SCHEMA_ID)

    async def test_parent_renamed_in_candidate_schema_success(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, region_schema_with_id: None
    ) -> None:
        candidate_schema = registry.schema.get_schema_branch(name=default_branch_scope_class.name).duplicate()
        renamed_kind = _rename_kind(schema_branch=candidate_schema, kind="LocationRegion", name="Territory")
        site_schema = candidate_schema.get_node(name="LocationSite")
        site_schema.parent = renamed_kind
        candidate_schema.set(name="LocationSite", schema=site_schema)

        request = SchemaConstraintValidatorRequest(
            branch=default_branch_scope_class,
            constraint_name="node.parent.update",
            node_schema=site_schema,
            schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="parent"),
            schema_branch=candidate_schema,
        )

        grouped_data_paths = await NodeHierarchyChecker(db=db, branch=default_branch_scope_class).check(request)

        assert [grouped.get_all_data_paths() for grouped in grouped_data_paths] == [[]]

    async def test_parent_renamed_on_branch_success(self, db: InfrahubDatabase, region_schema_with_id: None) -> None:
        branch = await create_branch(db=db, branch_name="renamed-region")
        branch_schema = registry.schema.get_schema_branch(name=branch.name)
        renamed_kind = _rename_kind(schema_branch=branch_schema, kind="LocationRegion", name="Territory")
        site_schema = branch_schema.get_node(name="LocationSite")
        site_schema.parent = renamed_kind
        branch_schema.set(name="LocationSite", schema=site_schema)

        request = SchemaConstraintValidatorRequest(
            branch=branch,
            constraint_name="node.parent.update",
            node_schema=site_schema,
            schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="parent"),
            schema_branch=branch_schema,
        )

        grouped_data_paths = await NodeHierarchyChecker(db=db, branch=branch).check(request)

        assert [grouped.get_all_data_paths() for grouped in grouped_data_paths] == [[]]

    async def test_site_parent_changed_to_renamed_rack_kind_refuses_region_parents(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        hierarchical_location_data_simple_scope_class: dict[str, Node],
        region_schema_with_id: None,
    ) -> None:
        """The change points LocationSite.parent at the renamed rack kind while the stored sites keep regions as parents.

        Only LocationRack, the rack kind's earlier name, is added to the allowed kinds, so every site is refused.
        """
        nodes = hierarchical_location_data_simple_scope_class
        candidate_schema = registry.schema.get_schema_branch(name=default_branch_scope_class.name).duplicate()
        renamed_kind = _rename_kind(schema_branch=candidate_schema, kind="LocationRack", name="Shelf")
        site_schema = candidate_schema.get_node(name="LocationSite")
        site_schema.parent = renamed_kind
        candidate_schema.set(name="LocationSite", schema=site_schema)

        request = SchemaConstraintValidatorRequest(
            branch=default_branch_scope_class,
            constraint_name="node.parent.update",
            node_schema=site_schema,
            schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="parent"),
            schema_branch=candidate_schema,
        )

        grouped_data_paths = await NodeHierarchyChecker(db=db, branch=default_branch_scope_class).check(request)

        assert len(grouped_data_paths) == 1
        assert {(dp.node_id, dp.peer_id) for dp in grouped_data_paths[0].get_all_data_paths()} == {
            (nodes["paris"].id, nodes["europe"].id),
            (nodes["london"].id, nodes["europe"].id),
            (nodes["chicago"].id, nodes["north-america"].id),
            (nodes["seattle"].id, nodes["north-america"].id),
            (nodes["beijing"].id, nodes["asia"].id),
            (nodes["singapore"].id, nodes["asia"].id),
        }
