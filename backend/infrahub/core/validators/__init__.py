from infrahub.core.validators.attribute.min_max import AttributeNumberChecker

from .attribute.choices import AttributeChoicesChecker
from .attribute.enum import AttributeEnumChecker
from .attribute.kind import AttributeKindChecker
from .attribute.length import AttributeLengthChecker
from .attribute.number_pool import AttributeNumberPoolChecker
from .attribute.optional import AttributeOptionalChecker
from .attribute.regex import AttributeRegexChecker
from .attribute.unique import AttributeUniquenessChecker
from .enum import ConstraintIdentifier
from .interface import ConstraintCheckerInterface
from .node.attribute import NodeAttributeAddChecker
from .node.generate_profile import NodeGenerateProfileChecker
from .node.hierarchy import NodeHierarchyChecker
from .node.inherit_from import NodeInheritFromChecker
from .node.relationship import NodeRelationshipAddChecker
from .relationship.count import RelationshipCountChecker
from .relationship.optional import RelationshipOptionalChecker
from .relationship.peer import RelationshipPeerChecker
from .uniqueness.checker import UniquenessChecker

CONSTRAINT_VALIDATOR_MAP: dict[str, type[ConstraintCheckerInterface] | None] = {
    "attribute.kind.update": AttributeKindChecker,
    "attribute.regex.update": AttributeRegexChecker,
    ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value: AttributeRegexChecker,
    "attribute.enum.update": AttributeEnumChecker,
    "attribute.min_length.update": AttributeLengthChecker,
    "attribute.max_length.update": AttributeLengthChecker,
    ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MIN_LENGTH_UPDATE.value: AttributeLengthChecker,
    ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MAX_LENGTH_UPDATE.value: AttributeLengthChecker,
    ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MIN_VALUE_UPDATE.value: AttributeNumberChecker,
    ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MAX_VALUE_UPDATE.value: AttributeNumberChecker,
    ConstraintIdentifier.ATTRIBUTE_PARAMETERS_EXCLUDED_VALUES_UPDATE.value: AttributeNumberChecker,
    ConstraintIdentifier.ATTRIBUTE_PARAMETERS_START_RANGE_UPDATE: AttributeNumberPoolChecker,
    ConstraintIdentifier.ATTRIBUTE_PARAMETERS_END_RANGE_UPDATE: AttributeNumberPoolChecker,
    "attribute.unique.update": AttributeUniquenessChecker,
    "attribute.optional.update": AttributeOptionalChecker,
    "attribute.choices.update": AttributeChoicesChecker,
    "relationship.peer.update": RelationshipPeerChecker,
    "relationship.cardinality.update": RelationshipCountChecker,
    "relationship.optional.update": RelationshipOptionalChecker,
    "relationship.min_count.update": RelationshipCountChecker,
    "relationship.max_count.update": RelationshipCountChecker,
    "node.inherit_from.update": NodeInheritFromChecker,
    "node.uniqueness_constraints.update": UniquenessChecker,
    "node.parent.update": NodeHierarchyChecker,
    "node.children.update": NodeHierarchyChecker,
    "node.generate_profile.update": NodeGenerateProfileChecker,
    "node.attribute.add": NodeAttributeAddChecker,
    "node.relationship.add": NodeRelationshipAddChecker,
}
