"""Relabelling of the Profile/Template kinds generated from a node when that node's kind changes.

The schema diff only reports nodes and generics, so the generated kinds ride along with the
migration of the kind they derive from rather than getting migrations of their own.
"""

from copy import deepcopy
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, RelationshipKind, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.schema.tasks import get_derived_schema_pairs
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_graph

GADGET_THING = GenericSchema(
    name="Thing",
    namespace="Testing",
    attributes=[AttributeSchema(name="nbr_things", kind="Number", optional=True)],
)

GADGET = NodeSchema(
    name="Gadget",
    namespace="Testing",
    generate_template=True,
    attributes=[AttributeSchema(name="name", kind="Text")],
)


def _profile_labels(kind: str) -> set[str]:
    """A profile's labels never depend on the generics of the node it derives from."""
    return {kind, "LineageSource", "CoreProfile", "CoreNode", "Node"}


async def _get_active_labels_by_uuid(db: InfrahubDatabase, kind: str, branch_name: str) -> dict[str, set[str]]:
    """Return ``{node uuid: labels}`` for the vertex of ``kind`` currently active on ``branch_name``.

    A kind update leaves the superseded vertex in place with its old labels, so the branch and the
    still-open IS_PART_OF edge are what identify the vertex a reader would resolve.
    """
    query = """
    MATCH (n:%(kind)s)-[r:IS_PART_OF {status: "active"}]->(:Root)
    WHERE r.branch = $branch_name AND r.to IS NULL
    RETURN n.uuid AS uuid, labels(n) AS labels
    """ % {"kind": kind}
    results = await db.execute_query(query=query, params={"branch_name": branch_name})
    return {row["uuid"]: set(row["labels"]) for row in results}


async def _migrate_node_kind(
    db: InfrahubDatabase, branch: Branch, current_kind: str, **changes: Any
) -> MigrationResult:
    """Apply ``changes`` to the TestingGadget node schema, then run the migration."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=current_kind)

    candidate_schema = schema.duplicate()
    new_node = candidate_schema.get(name=current_kind)
    candidate_schema.delete(name=current_kind)
    for field_name, value in changes.items():
        setattr(new_node, field_name, value)
    candidate_schema.set(name=new_node.kind, schema=new_node)
    candidate_schema.process()

    migration = NodeKindUpdateMigration(
        previous_node_schema=previous_node,
        new_node_schema=new_node,
        derived_schemas=get_derived_schema_pairs(
            previous_schema_branch=schema,
            new_schema_branch=candidate_schema,
            previous_node_schema=previous_node,
            new_node_schema=new_node,
        ),
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=new_node.kind, field_name=sorted(changes)[0]
        ),
    )
    registry.schema.set_schema_branch(name=branch.name, schema=candidate_schema)
    return await migration.execute(migration_input=MigrationInput(db=db), branch=branch)


class TestGeneratedKindRelabelling:
    """Relabelling of the generated Profile/Template kinds when their source kind changes.

    The tests share one schema and one set of vertices and run in order, each building on the
    graph the previous one left behind.
    """

    @pytest.fixture(scope="class")
    async def gadget_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SchemaBranch:
        registry.schema.register_schema(
            schema=SchemaRoot(generics=[core_object_template, core_object_component_template]),
            branch=default_branch_scope_class.name,
        )
        return registry.schema.register_schema(
            schema=SchemaRoot(generics=[deepcopy(GADGET_THING)], nodes=[deepcopy(GADGET)]),
            branch=default_branch_scope_class.name,
        )

    @pytest.fixture(scope="class")
    async def gadget_data(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, gadget_schema: SchemaBranch
    ) -> dict[str, str]:
        gadget = await Node.init(db=db, schema="TestingGadget", branch=default_branch_scope_class)
        await gadget.new(db=db, name="gadget-1")
        await gadget.save(db=db)

        profile = await Node.init(db=db, schema="ProfileTestingGadget", branch=default_branch_scope_class)
        await profile.new(db=db, profile_name="gadget-profile-1")
        await profile.save(db=db)

        template = await Node.init(db=db, schema="TemplateTestingGadget", branch=default_branch_scope_class)
        await template.new(db=db, template_name="Gadget Template 1")
        await template.save(db=db)

        return {"gadget": gadget.id, "profile": profile.id, "template": template.id}

    async def test_template_starts_without_the_generic_label(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, gadget_data: dict[str, str]
    ) -> None:
        labels_map = await _get_active_labels_by_uuid(
            db=db, kind="TemplateTestingGadget", branch_name=default_branch_scope_class.name
        )
        template_uuid = gadget_data["template"]
        assert set(labels_map) == {template_uuid}
        assert "TemplateTestingThing" not in labels_map[template_uuid]
        assert await count_nodes(db=db, label="TemplateTestingThing") == 0

        profile_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="ProfileTestingGadget", branch_name=default_branch_scope_class.name
        )
        assert profile_labels_map == {gadget_data["profile"]: _profile_labels(kind="ProfileTestingGadget")}

    async def test_template_gains_generic_label_when_kind_inherits_generic(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, gadget_data: dict[str, str]
    ) -> None:
        """A template created before its kind inherits a generic must join the generic's template kind."""
        execution_result = await _migrate_node_kind(
            db=db, branch=default_branch_scope_class, current_kind="TestingGadget", inherit_from=["TestingThing"]
        )

        assert not execution_result.errors
        # the gadget and its template move; the profile's labels do not depend on the node's generics
        assert execution_result.nbr_migrations_executed == 2

        labels_map = await _get_active_labels_by_uuid(
            db=db, kind="TemplateTestingGadget", branch_name=default_branch_scope_class.name
        )
        template_uuid = gadget_data["template"]
        assert set(labels_map) == {template_uuid}
        assert "TemplateTestingThing" in labels_map[template_uuid]
        assert await count_nodes(db=db, label="TemplateTestingThing") == 1

        profile_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="ProfileTestingGadget", branch_name=default_branch_scope_class.name
        )
        assert profile_labels_map == {gadget_data["profile"]: _profile_labels(kind="ProfileTestingGadget")}
        assert await count_nodes(db=db, label="ProfileTestingGadget") == 1
        await verify_graph(db=db)

    async def test_relabelling_is_idempotent(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, gadget_data: dict[str, str]
    ) -> None:
        """Re-running the same migration must not duplicate the vertices a second time."""
        count_rels_before = await count_relationships(db=db)

        execution_result = await _migrate_node_kind(
            db=db, branch=default_branch_scope_class, current_kind="TestingGadget", inherit_from=["TestingThing"]
        )

        assert not execution_result.errors
        assert execution_result.nbr_migrations_executed == 0
        assert await count_relationships(db=db) == count_rels_before
        # the kind label is unchanged, so it stays on the superseded vertex as well as its replacement
        assert await count_nodes(db=db, label="TemplateTestingGadget") == 2
        assert await count_nodes(db=db, label="TemplateTestingThing") == 1

    async def test_template_loses_generic_label_when_kind_drops_generic(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, gadget_data: dict[str, str]
    ) -> None:
        """Dropping the generic must stop the template matching the generic's template kind."""
        execution_result = await _migrate_node_kind(
            db=db, branch=default_branch_scope_class, current_kind="TestingGadget", inherit_from=[]
        )

        assert not execution_result.errors
        assert execution_result.nbr_migrations_executed == 2

        labels_map = await _get_active_labels_by_uuid(
            db=db, kind="TemplateTestingGadget", branch_name=default_branch_scope_class.name
        )
        template_uuid = gadget_data["template"]
        assert set(labels_map) == {template_uuid}
        assert "TemplateTestingThing" not in labels_map[template_uuid]

        profile_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="ProfileTestingGadget", branch_name=default_branch_scope_class.name
        )
        assert profile_labels_map == {gadget_data["profile"]: _profile_labels(kind="ProfileTestingGadget")}
        await verify_graph(db=db)

    async def test_kind_rename_relabels_profile_and_template(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, gadget_data: dict[str, str]
    ) -> None:
        """A rename changes the generated kinds' names too, so their vertices must follow."""
        assert await count_nodes(db=db, label="ProfileTesting2NewGadget") == 0
        assert await count_nodes(db=db, label="TemplateTesting2NewGadget") == 0

        execution_result = await _migrate_node_kind(
            db=db,
            branch=default_branch_scope_class,
            current_kind="TestingGadget",
            name="NewGadget",
            namespace="Testing2",
        )

        assert not execution_result.errors
        assert execution_result.nbr_migrations_executed == 3

        assert await count_nodes(db=db, label="Testing2NewGadget") == 1
        assert await count_nodes(db=db, label="ProfileTesting2NewGadget") == 1
        assert await count_nodes(db=db, label="TemplateTesting2NewGadget") == 1

        renamed_profile_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="ProfileTesting2NewGadget", branch_name=default_branch_scope_class.name
        )
        assert renamed_profile_labels_map == {gadget_data["profile"]: _profile_labels(kind="ProfileTesting2NewGadget")}

        renamed_template_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="TemplateTesting2NewGadget", branch_name=default_branch_scope_class.name
        )
        assert set(renamed_template_labels_map) == {gadget_data["template"]}
        await verify_graph(db=db)

    async def test_relabelling_on_a_branch_leaves_the_default_branch_alone(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, gadget_data: dict[str, str]
    ) -> None:
        """Labels live on the vertex, so a branch's schema change must reach readers only via its edges."""
        branch = await create_branch(db=db, branch_name="gadget-inherit-branch")

        execution_result = await _migrate_node_kind(
            db=db, branch=branch, current_kind="Testing2NewGadget", inherit_from=["TestingThing"]
        )

        assert not execution_result.errors
        assert execution_result.nbr_migrations_executed == 2

        on_branch_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="TemplateTesting2NewGadget", branch_name=branch.name
        )
        assert set(on_branch_labels_map) == {gadget_data["template"]}
        assert "TemplateTestingThing" in on_branch_labels_map[gadget_data["template"]]

        on_main_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="TemplateTesting2NewGadget", branch_name=default_branch_scope_class.name
        )
        assert set(on_main_labels_map) == {gadget_data["template"]}
        assert "TemplateTestingThing" not in on_main_labels_map[gadget_data["template"]]

        # an inheritance change leaves the profile alone, so the branch gets no profile vertex of its
        # own and readers on it fall through to the one the default branch still owns
        branch_profile_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="ProfileTesting2NewGadget", branch_name=branch.name
        )
        assert branch_profile_labels_map == {}
        main_profile_labels_map = await _get_active_labels_by_uuid(
            db=db, kind="ProfileTesting2NewGadget", branch_name=default_branch_scope_class.name
        )
        assert main_profile_labels_map == {gadget_data["profile"]: _profile_labels(kind="ProfileTesting2NewGadget")}

        await verify_graph(db=db)


WIDGET_THING = GenericSchema(
    name="Thing",
    namespace="Sub",
    attributes=[AttributeSchema(name="nbr_things", kind="Number", optional=True)],
)

WIDGET_HOLDER = NodeSchema(
    name="Holder",
    namespace="Sub",
    generate_template=True,
    attributes=[AttributeSchema(name="name", kind="Text")],
    relationships=[
        RelationshipSchema(
            name="parts",
            peer="SubPart",
            kind=RelationshipKind.COMPONENT,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
        )
    ],
)

# generates neither a template nor a profile of its own, but is a component peer of SubHolder
WIDGET_PART = NodeSchema(
    name="Part",
    namespace="Sub",
    generate_template=False,
    generate_profile=False,
    attributes=[AttributeSchema(name="name", kind="Text")],
)


class TestSubtemplateRelabelling:
    """Relabelling of a subtemplate, which exists even though its kind sets generate_template=False.

    A kind pulled in as a component peer of a template-generating kind still gets a Template kind,
    built on CoreObjectComponentTemplate rather than CoreObjectTemplate, and it still joins the
    template kinds of any generics it inherits. A profile has no equivalent path.
    """

    @pytest.fixture(scope="class")
    async def subtemplate_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SchemaBranch:
        registry.schema.register_schema(
            schema=SchemaRoot(generics=[core_object_template, core_object_component_template]),
            branch=default_branch_scope_class.name,
        )
        return registry.schema.register_schema(
            schema=SchemaRoot(
                generics=[deepcopy(WIDGET_THING)], nodes=[deepcopy(WIDGET_HOLDER), deepcopy(WIDGET_PART)]
            ),
            branch=default_branch_scope_class.name,
        )

    @pytest.fixture(scope="class")
    async def subtemplate_data(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, subtemplate_schema: SchemaBranch
    ) -> dict[str, str]:
        subtemplate = await Node.init(db=db, schema="TemplateSubPart", branch=default_branch_scope_class)
        # a subtemplate keeps the optionality of the source attribute, so name is mandatory here
        await subtemplate.new(db=db, template_name="Part Template 1", name="part-1")
        await subtemplate.save(db=db)
        return {"subtemplate": subtemplate.id}

    async def test_subtemplate_exists_without_generate_template(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, subtemplate_data: dict[str, str]
    ) -> None:
        """The component peer has a Template kind and instances despite generate_template=False."""
        schema = registry.schema.get_schema_branch(name=default_branch_scope_class.name)
        assert schema.get_node(name="SubPart", duplicate=False).generate_template is False
        assert not schema.has(name="ProfileSubPart")

        labels_map = await _get_active_labels_by_uuid(
            db=db, kind="TemplateSubPart", branch_name=default_branch_scope_class.name
        )
        subtemplate_uuid = subtemplate_data["subtemplate"]
        assert set(labels_map) == {subtemplate_uuid}
        assert "CoreObjectComponentTemplate" in labels_map[subtemplate_uuid]
        assert "CoreObjectTemplate" not in labels_map[subtemplate_uuid]
        assert "TemplateSubThing" not in labels_map[subtemplate_uuid]

    async def test_subtemplate_joins_the_generic_template_kind(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, subtemplate_data: dict[str, str]
    ) -> None:
        """The component peer inheriting a generic must pull its subtemplate into the generic's template kind."""
        execution_result = await _migrate_node_kind(
            db=db,
            branch=default_branch_scope_class,
            current_kind="SubPart",
            inherit_from=["SubThing"],
        )

        assert not execution_result.errors
        assert execution_result.nbr_migrations_executed == 1

        labels_map = await _get_active_labels_by_uuid(
            db=db, kind="TemplateSubPart", branch_name=default_branch_scope_class.name
        )
        subtemplate_uuid = subtemplate_data["subtemplate"]
        assert set(labels_map) == {subtemplate_uuid}
        assert "TemplateSubThing" in labels_map[subtemplate_uuid]
        # the subtemplate stays a component template rather than being promoted
        assert "CoreObjectComponentTemplate" in labels_map[subtemplate_uuid]
        assert "CoreObjectTemplate" not in labels_map[subtemplate_uuid]
        await verify_graph(db=db)
