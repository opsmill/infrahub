from typing import Dict, Optional, Type

from .attribute.choices import AttributeChoicesChecker
from .attribute.enum import AttributeEnumChecker
from .attribute.optional import AttributeOptionalChecker
from .attribute.regex import AttributeRegexChecker
from .attribute.unique import AttributeUniquenessChecker
from .interface import ConstraintCheckerInterface
from .relationship.optional import RelationshipOptionalChecker
from .uniqueness.checker import UniquenessChecker

CONSTRAINT_VALIDATOR_MAP: Dict[str, Optional[Type[ConstraintCheckerInterface]]] = {
    "attribute.regex.update": AttributeRegexChecker,
    "attribute.enum.update": AttributeEnumChecker,
    "attribute.min_length.update": None,
    "attribute.max_length.update": None,
    "attribute.unique.update": AttributeUniquenessChecker,
    "attribute.optional.update": AttributeOptionalChecker,
    "attribute.choices.update": AttributeChoicesChecker,
    "relationship.peer.update": None,
    "relationship.cardinality.update": None,
    "relationship.optional.update": RelationshipOptionalChecker,
    "relationship.min_count.update": None,
    "relationship.max_count.update": None,
    "node.uniqueness_constraints.update": UniquenessChecker,
    "node.hierarchical.update": None,  # Generic
    "node.hierarchy.update": None,
    "node.parent.update": None,
    "node.children.update": None,
}
