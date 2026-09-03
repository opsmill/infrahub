"""Schemas whose branch support disagrees with that of their own fields.

A field with no explicit ``branch`` inherits the parent kind's support, so every mismatch has to be
declared. The aware-kind mismatches come from :mod:`tests.helpers.schema.agnostic_retirement`, whose
``AgnosticretireWidget`` already declares both an agnostic attribute and an agnostic relationship on
an aware kind; the agnostic-kind mismatches have no such instance and are declared here.
"""

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA

AGNOSTIC_KIND_AWARE_ATTRIBUTES_SCHEMA = NodeSchema(
    name="MetaMirror",
    namespace="Test",
    default_filter="name__value",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(
            name="name",
            kind="Text",
            branch=BranchSupportType.AWARE,
        ),
        AttributeSchema(
            name="ref",
            kind="Text",
            branch=BranchSupportType.AWARE,
            optional=True,
        ),
    ],
)
"""An agnostic kind, ``TestMetaMirror``, whose every attribute is branch-aware."""


AGNOSTIC_KIND_WITH_RELATIONSHIP_SCHEMA = NodeSchema(
    name="MetaMirrorPeer",
    namespace="Test",
    default_filter="name__value",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(
            name="name",
            kind="Text",
            branch=BranchSupportType.AWARE,
        ),
    ],
    relationships=[
        RelationshipSchema(
            name="mirror",
            peer="TestMetaMirror",
            optional=True,
            cardinality=RelationshipCardinality.ONE,
            identifier="test__metamirror__peer",
        ),
    ],
)
"""An agnostic kind with an aware attribute and an agnostic relationship."""


def register_branch_support_mismatch_schemas(branch: Branch) -> None:
    """Register the branch-support-mismatch schemas on ``branch``.

    Args:
        branch: Branch to register the schemas on. Use the default branch: the invariant is about
            what a default-branch read returns.

    """
    registry.schema.register_schema(
        schema=SchemaRoot(
            nodes=[
                *AGNOSTIC_RETIREMENT_SCHEMA.nodes,
                AGNOSTIC_KIND_AWARE_ATTRIBUTES_SCHEMA,
                AGNOSTIC_KIND_WITH_RELATIONSHIP_SCHEMA,
            ]
        ),
        branch=branch.name,
    )
