from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.queries import SchemaSummaryQuery
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestSchemaSummaryQuery:
    @pytest.fixture(scope="class")
    async def schemas_loaded(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_internal_models_schema_scope_class: SchemaBranch,
    ) -> None:
        """Load four schemas covering attrs-only, rels-only, both, and neither."""
        user_schema = SchemaRoot(
            nodes=[
                NodeSchema(
                    name="AttrsOnly",
                    namespace="Querytest",
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                        AttributeSchema(name="color", kind="Text", optional=True),
                    ],
                ),
                NodeSchema(
                    name="RelsOnly",
                    namespace="Querytest",
                    relationships=[
                        RelationshipSchema(
                            name="primary_owner",
                            peer="QuerytestAttrsOnly",
                            optional=True,
                            cardinality=RelationshipCardinality.ONE,
                        ),
                    ],
                ),
                NodeSchema(
                    name="Both",
                    namespace="Querytest",
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                        AttributeSchema(name="description", kind="Text", optional=True),
                    ],
                    relationships=[
                        RelationshipSchema(
                            name="secondary_owner",
                            peer="QuerytestAttrsOnly",
                            optional=True,
                            cardinality=RelationshipCardinality.ONE,
                        ),
                    ],
                ),
                NodeSchema(name="Neither", namespace="Querytest"),
            ],
        )
        schema_branch = registry.schema.register_schema(schema=user_schema, branch=default_branch_scope_class.name)
        kinds = ["QuerytestAttrsOnly", "QuerytestRelsOnly", "QuerytestBoth", "QuerytestNeither"]
        await registry.schema.load_schema_to_db(
            schema=schema_branch,
            db=db,
            branch=default_branch_scope_class,
            limit=kinds,
            at=Timestamp(),
        )

    async def test_kind_filter_single(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """kind_filter limits results to the requested (namespace, name) pair."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "AttrsOnly")],
        )
        await query.execute(db=db)
        assert query.get_summaries().get_kinds() == {"QuerytestAttrsOnly"}

    async def test_kind_filter_multiple(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """kind_filter with multiple pairs returns each of them."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "AttrsOnly"), ("Querytest", "Both")],
        )
        await query.execute(db=db)
        assert query.get_summaries().get_kinds() == {"QuerytestAttrsOnly", "QuerytestBoth"}

    async def test_kind_filter_nonexistent(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """kind_filter for a non-existent kind returns an empty result."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "DoesNotExist")],
        )
        await query.execute(db=db)
        assert len(query.get_summaries()) == 0

    async def test_no_kind_filter_includes_all_test_kinds(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """kind_filter=None returns every kind on the branch (incl. internal models)."""
        query = await SchemaSummaryQuery.init(db=db, branch=default_branch_scope_class)
        await query.execute(db=db)
        summaries = query.get_summaries()
        for kind in ("QuerytestAttrsOnly", "QuerytestRelsOnly", "QuerytestBoth", "QuerytestNeither"):
            assert kind in summaries.get_kinds()

    async def test_attribute_names_none_returns_all(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """attribute_names=None returns every active attribute of the parent."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "AttrsOnly")],
            attribute_names=None,
        )
        await query.execute(db=db)
        summary = query.get_summaries().get_summary_by_kind(kind="QuerytestAttrsOnly")
        assert summary is not None
        assert set(summary.attributes.keys()) == {"name", "color"}

    async def test_attribute_names_empty_returns_none_but_preserves_parent(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """attribute_names=[] drops every attribute but the parent row is still returned."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "AttrsOnly")],
            attribute_names=[],
        )
        await query.execute(db=db)
        summaries = query.get_summaries()
        assert "QuerytestAttrsOnly" in summaries.get_kinds()
        summary = summaries.get_summary_by_kind(kind="QuerytestAttrsOnly")
        assert summary is not None
        assert summary.attributes == {}

    async def test_attribute_names_specific(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """attribute_names=['name'] returns only the ``name`` attribute."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "AttrsOnly")],
            attribute_names=["name"],
        )
        await query.execute(db=db)
        summary = query.get_summaries().get_summary_by_kind(kind="QuerytestAttrsOnly")
        assert summary is not None
        assert set(summary.attributes.keys()) == {"name"}

    async def test_attribute_names_no_match_preserves_parent(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """attribute_names with a name that doesn't exist returns empty attrs and keeps parent."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "AttrsOnly")],
            attribute_names=["does_not_exist"],
        )
        await query.execute(db=db)
        summaries = query.get_summaries()
        assert "QuerytestAttrsOnly" in summaries.get_kinds()
        summary = summaries.get_summary_by_kind(kind="QuerytestAttrsOnly")
        assert summary is not None
        assert summary.attributes == {}

    async def test_relationship_names_none_returns_all(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """relationship_names=None returns every active relationship."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "Both")],
            relationship_names=None,
        )
        await query.execute(db=db)
        summary = query.get_summaries().get_summary_by_kind(kind="QuerytestBoth")
        assert summary is not None
        assert set(summary.relationships.keys()) == {"secondary_owner"}

    async def test_relationship_names_empty_returns_none_but_preserves_parent(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """relationship_names=[] drops every relationship but the parent row is still returned."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "Both")],
            relationship_names=[],
        )
        await query.execute(db=db)
        summaries = query.get_summaries()
        assert "QuerytestBoth" in summaries.get_kinds()
        summary = summaries.get_summary_by_kind(kind="QuerytestBoth")
        assert summary is not None
        assert summary.relationships == {}

    async def test_relationship_names_specific(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """relationship_names=[name] returns only that matching relationship."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "Both")],
            relationship_names=["secondary_owner"],
        )
        await query.execute(db=db)
        summary = query.get_summaries().get_summary_by_kind(kind="QuerytestBoth")
        assert summary is not None
        assert set(summary.relationships.keys()) == {"secondary_owner"}

    async def test_schema_with_attributes_only(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """A schema with attributes but no relationships returns populated attrs, empty rels."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "AttrsOnly")],
        )
        await query.execute(db=db)
        summary = query.get_summaries().get_summary_by_kind(kind="QuerytestAttrsOnly")
        assert summary is not None
        assert set(summary.attributes.keys()) == {"name", "color"}
        assert summary.relationships == {}

    async def test_schema_with_relationships_only(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """A schema with relationships but no attributes returns empty attrs, populated rels."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "RelsOnly")],
        )
        await query.execute(db=db)
        summary = query.get_summaries().get_summary_by_kind(kind="QuerytestRelsOnly")
        assert summary is not None
        assert summary.attributes == {}
        assert set(summary.relationships.keys()) == {"primary_owner"}

    async def test_schema_with_both(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """A schema with both attributes and relationships returns both populated."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "Both")],
        )
        await query.execute(db=db)
        summary = query.get_summaries().get_summary_by_kind(kind="QuerytestBoth")
        assert summary is not None
        assert set(summary.attributes.keys()) == {"name", "description"}
        assert set(summary.relationships.keys()) == {"secondary_owner"}

    async def test_schema_with_neither(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        schemas_loaded: None,
    ) -> None:
        """A schema with neither attributes nor relationships returns both empty."""
        query = await SchemaSummaryQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_filter=[("Querytest", "Neither")],
        )
        await query.execute(db=db)
        summary = query.get_summaries().get_summary_by_kind(kind="QuerytestNeither")
        assert summary is not None
        assert summary.is_generic is False
        assert summary.uuid
        assert summary.attributes == {}
        assert summary.relationships == {}
