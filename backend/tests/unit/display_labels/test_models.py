from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.display_labels.models import DisplayLabelJinja2GraphQL


def test_query_fields_uses_inline_fragment_for_hierarchical_relationship() -> None:
    """query_fields wraps peer-only attributes in an inline fragment when the relationship is hierarchical."""
    site_schema = NodeSchema(
        name="Site",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="shortname", kind="Text"),
            AttributeSchema(name="slug", kind="Text"),
        ],
        relationships=[
            RelationshipSchema(
                name="parent",
                peer="TestingCountry",
                hierarchical="TestingLocation",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )

    graphql_obj = DisplayLabelJinja2GraphQL(
        filter_key="ids",
        node_schema=site_schema,
        variables=["parent__slug__value", "shortname__value"],
    )

    fields = graphql_obj.query_fields

    # shortname is a direct attribute — should be at the top level
    assert fields["shortname"] == {"value": None}

    # parent.node must use an inline fragment for the concrete peer type
    parent_node = fields["parent"]["node"]
    assert "... on TestingCountry" in parent_node, (
        f"Expected inline fragment '... on TestingCountry' in parent node fields, got: {parent_node}"
    )
    assert parent_node["... on TestingCountry"]["slug"] == {"value": None}

    # The rendered query must contain the inline fragment syntax
    rendered = graphql_obj.render_graphql_query(filter_id="abc-123")
    assert "... on TestingCountry" in rendered


def test_query_fields_no_fragment_for_non_hierarchical_relationship() -> None:
    """query_fields places attributes directly under node when the relationship is not hierarchical."""
    schema = NodeSchema(
        name="Site",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="slug", kind="Text"),
        ],
        relationships=[
            RelationshipSchema(
                name="owner",
                peer="TestingCountry",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )

    graphql_obj = DisplayLabelJinja2GraphQL(
        filter_key="ids",
        node_schema=schema,
        variables=["owner__name__value"],
    )

    fields = graphql_obj.query_fields
    parent_node = fields["owner"]["node"]

    assert "name" in parent_node
    assert parent_node["name"] == {"value": None}
    assert not any(k.startswith("... on") for k in parent_node)


def test_query_fields_no_fragment_when_peer_equals_hierarchical() -> None:
    """query_fields places attributes directly under node when peer is the hierarchy generic itself."""
    schema = NodeSchema(
        name="Site",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="slug", kind="Text"),
        ],
        relationships=[
            RelationshipSchema(
                name="parent",
                peer="TestingLocation",
                hierarchical="TestingLocation",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )

    graphql_obj = DisplayLabelJinja2GraphQL(
        filter_key="ids",
        node_schema=schema,
        variables=["parent__name__value"],
    )

    fields = graphql_obj.query_fields
    parent_node = fields["parent"]["node"]

    assert "name" in parent_node
    assert parent_node["name"] == {"value": None}
    assert not any(k.startswith("... on") for k in parent_node)
