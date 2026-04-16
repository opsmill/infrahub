from collections.abc import Callable

import pytest

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.display_labels.models import DisplayLabelJinja2GraphQL


class TestQueryFieldsInlineFragment:
    @pytest.fixture(scope="class")
    def build_schema(self) -> Callable[..., NodeSchema]:
        def _build(
            relationship_name: str = "parent",
            peer: str = "TestingCountry",
            hierarchical: str | None = "TestingLocation",
        ) -> NodeSchema:
            return NodeSchema(
                name="Site",
                namespace="Testing",
                attributes=[
                    AttributeSchema(name="shortname", kind="Text"),
                    AttributeSchema(name="slug", kind="Text"),
                ],
                relationships=[
                    RelationshipSchema(
                        name=relationship_name,
                        peer=peer,
                        hierarchical=hierarchical,
                        cardinality=RelationshipCardinality.ONE,
                        optional=False,
                    ),
                ],
            )

        return _build

    def test_uses_fragment_when_peer_differs_from_hierarchical(self, build_schema: Callable[..., NodeSchema]) -> None:
        """query_fields wraps attributes in an inline fragment when peer != hierarchical."""
        schema = build_schema(peer="TestingCountry", hierarchical="TestingLocation")
        graphql_obj = DisplayLabelJinja2GraphQL(
            filter_key="ids",
            node_schema=schema,
            variables=["parent__slug__value", "shortname__value"],
        )

        fields = graphql_obj.query_fields

        assert fields["shortname"] == {"value": None}
        parent_node = fields["parent"]["node"]
        assert "... on TestingCountry" in parent_node, (
            f"Expected inline fragment '... on TestingCountry' in parent node fields, got: {parent_node}"
        )
        assert parent_node["... on TestingCountry"]["slug"] == {"value": None}

        rendered = graphql_obj.render_graphql_query(filter_id="abc-123")
        assert "... on TestingCountry" in rendered

    def test_no_fragment_for_non_hierarchical_relationship(self, build_schema: Callable[..., NodeSchema]) -> None:
        """query_fields places attributes directly under node when relationship is not hierarchical."""
        schema = build_schema(relationship_name="owner", peer="TestingCountry", hierarchical=None)
        graphql_obj = DisplayLabelJinja2GraphQL(
            filter_key="ids",
            node_schema=schema,
            variables=["owner__name__value"],
        )

        fields = graphql_obj.query_fields
        owner_node = fields["owner"]["node"]

        assert owner_node["name"] == {"value": None}
        assert not any(k.startswith("... on") for k in owner_node)

    def test_no_fragment_when_peer_equals_hierarchical(self, build_schema: Callable[..., NodeSchema]) -> None:
        """query_fields places attributes directly under node when peer is the hierarchy generic itself."""
        schema = build_schema(peer="TestingLocation", hierarchical="TestingLocation")
        graphql_obj = DisplayLabelJinja2GraphQL(
            filter_key="ids",
            node_schema=schema,
            variables=["parent__name__value"],
        )

        fields = graphql_obj.query_fields
        parent_node = fields["parent"]["node"]

        assert parent_node["name"] == {"value": None}
        assert not any(k.startswith("... on") for k in parent_node)
