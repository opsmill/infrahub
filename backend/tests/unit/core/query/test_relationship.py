import pytest

from infrahub.core.query.relationship import RelationshipGetByIdentifierQuery


def test_relationship_get_by_identifier_query_excluded_node_ids_requires_node_ids() -> None:
    with pytest.raises(ValueError, match=r"^excluded_node_ids requires node_ids$"):
        RelationshipGetByIdentifierQuery(identifiers=["testcar__testperson"], excluded_node_ids=["some-id"])
