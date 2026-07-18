import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

INTERNAL_KINDS = ["SchemaNode", "SchemaGeneric", "SchemaAttribute", "SchemaRelationship"]


def _build_candidate_schema(branch_schema: SchemaBranch) -> SchemaBranch:
    candidate_schema = branch_schema.duplicate()
    candidate_schema.load_schema(schema=SchemaRoot(**internal_schema))
    candidate_schema.load_schema(schema=SchemaRoot(**core_models))
    candidate_schema.load_schema(schema=SchemaRoot(**deprecated_models))
    candidate_schema.process()
    return candidate_schema


@pytest.fixture
async def persisted_core_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    """Persist the full code-defined schema, mirroring a converged installation."""
    schema_branch = registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.load_schema(schema=SchemaRoot(**deprecated_models))
    schema_branch.process()
    await registry.schema.load_schema_to_db(schema=schema_branch, branch=default_branch, db=db)
    return schema_branch


class TestCoreSchemaDiffFromDatabase:
    """The upgrade flow diffs the database schema against the code-defined schema.

    These tests pin the properties that make that diff trustworthy: the internal schema is
    persisted (and reloads with ids), an up-to-date database produces an empty diff, and a
    field newly defined in code is reported as added.
    """

    async def test_internal_schema_is_persisted_with_ids(
        self, db: InfrahubDatabase, default_branch: Branch, persisted_core_schema: SchemaBranch
    ) -> None:
        branch_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)

        for kind in INTERNAL_KINDS:
            node = branch_schema.get(name=kind, duplicate=False)
            assert node.id is not None
            assert all(attr.id is not None for attr in node.attributes)

    async def test_up_to_date_database_has_empty_diff(
        self, db: InfrahubDatabase, default_branch: Branch, persisted_core_schema: SchemaBranch
    ) -> None:
        branch_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        candidate_schema = _build_candidate_schema(branch_schema=branch_schema)

        schema_diff = branch_schema.diff(other=candidate_schema)

        assert schema_diff.all == []

    async def test_internal_field_added_in_code_is_reported_as_added(
        self, db: InfrahubDatabase, default_branch: Branch, persisted_core_schema: SchemaBranch
    ) -> None:
        # simulate a database created by an older release: one internal-schema attribute
        # does not exist in the database but is defined in code
        branch_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        schema_attribute = branch_schema.get(name="SchemaAttribute", duplicate=True)
        removed_attribute = schema_attribute.attributes[-1]
        schema_attribute.attributes = [
            attr for attr in schema_attribute.attributes if attr.name != removed_attribute.name
        ]
        branch_schema.set(name="SchemaAttribute", schema=schema_attribute)

        candidate_schema = _build_candidate_schema(branch_schema=branch_schema)
        schema_diff = branch_schema.diff(other=candidate_schema)

        assert list(schema_diff.changed) == ["SchemaAttribute"]
        node_diff = schema_diff.changed["SchemaAttribute"]
        assert node_diff is not None
        attrs_diff = node_diff.changed["attributes"]
        assert attrs_diff is not None
        assert removed_attribute.name in attrs_diff.added
