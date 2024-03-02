from typing import Dict, Optional, Type

from .attribute.choices import AttributeChoicesChecker
from .attribute.enum import AttributeEnumChecker
from .attribute.length import AttributeLengthChecker
from .attribute.optional import AttributeOptionalChecker
from .attribute.regex import AttributeRegexChecker
from .attribute.unique import AttributeUniquenessChecker
from .interface import ConstraintCheckerInterface
from .node.hierarchy import NodeHierarchyChecker
from .relationship.count import RelationshipCountChecker
from .relationship.optional import RelationshipOptionalChecker
from .relationship.peer import RelationshipPeerChecker
from .uniqueness.checker import UniquenessChecker

CONSTRAINT_VALIDATOR_MAP: Dict[str, Optional[Type[ConstraintCheckerInterface]]] = {
    "attribute.regex.update": AttributeRegexChecker,
    "attribute.enum.update": AttributeEnumChecker,
    "attribute.min_length.update": AttributeLengthChecker,
    "attribute.max_length.update": AttributeLengthChecker,
    "attribute.unique.update": AttributeUniquenessChecker,
    "attribute.optional.update": AttributeOptionalChecker,
    "attribute.choices.update": AttributeChoicesChecker,
    "relationship.peer.update": RelationshipPeerChecker,
    "relationship.cardinality.update": RelationshipCountChecker,
    "relationship.optional.update": RelationshipOptionalChecker,
    "relationship.min_count.update": RelationshipCountChecker,
    "relationship.max_count.update": RelationshipCountChecker,
    "node.uniqueness_constraints.update": UniquenessChecker,
    "node.parent.update": NodeHierarchyChecker,
    "node.children.update": NodeHierarchyChecker,
}
