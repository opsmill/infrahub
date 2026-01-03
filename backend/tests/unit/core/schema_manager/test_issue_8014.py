"""Test case for GitHub issue #8014.

Reproduces: KeyError when loading schema with inherited relationship
that doesn't exist in the parent generic.
"""

import pytest

from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch


def test_generate_weight_with_incorrectly_inherited_relationship():
    """Test that a relationship marked as inherited but not in generic raises a KeyError.

    This reproduces issue #8014 where a schema defines a relationship with
    `inherited: true` but the relationship doesn't exist in any generic
    that the node inherits from.

    The bug occurs in _generate_weight_nodes_profiles when it assumes
    that any field with `inherited: True` will be found in generic_fields_map.
    """
    schema_dict = {
        "nodes": [
            {
                "name": "City",
                "namespace": "Location",
                "inherit_from": ["LocationGeneric"],
                "attributes": [
                    {"name": "name", "kind": "Text"},
                ],
                "relationships": [
                    {
                        "name": "region",
                        "peer": "LocationRegion",
                        "cardinality": "one",
                        "optional": True,
                        # This is the bug trigger: relationship marked as inherited
                        # but "region" doesn't exist in LocationGeneric
                        "inherited": True,
                    },
                ],
            },
            {
                "name": "Region",
                "namespace": "Location",
                "inherit_from": ["LocationGeneric"],
                "attributes": [
                    {"name": "name", "kind": "Text"},
                ],
            },
        ],
        "generics": [
            {
                "name": "Generic",
                "namespace": "Location",
                "attributes": [
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                # Note: "region" relationship is NOT defined here
            },
        ],
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_dict))
    schema.process_inheritance()

    # This is where the KeyError occurs in _generate_weight_nodes_profiles
    # because "region" is marked as inherited but doesn't exist in the generic
    with pytest.raises(KeyError, match="region"):
        schema.generate_weight()
