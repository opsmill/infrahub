from typing import Dict, Optional, Type

from .attribute.regex import AttributeRegexUpdateValidator
from .shared import SchemaValidator

VALIDATOR_MAP: Dict[str, Optional[Type[SchemaValidator]]] = {
    "attribute.regex.update": AttributeRegexUpdateValidator,
    "attribute.enum.update": None,
    "attribute.min_lenght.update": None,
    "attribute.max_length.update": None,
    "attribute.unique.update": None,
    "attribute.optional.update": None,
    "attribute.choices.update": None,
    "relationship.peer.update": None,
    "relationship.cardinality.update": None,
    "relationship.optional.update": None,
    "relationship.min_count.update": None,
    "relationship.max_count.update": None,
    "node.uniqueness_constraints.update": None,
    "node.hierarchical.update": None,  # Generic
    "node.hierarchy.update": None,
    "node.parent.update": None,
    "node.children.update": None,
}
