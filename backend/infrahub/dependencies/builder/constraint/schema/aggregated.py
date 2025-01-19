from infrahub.core.validators.aggregated_checker import AggregatedConstraintChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .attribute_choices import SchemaAttributeChoicesConstraintDependency
from .attribute_enum import SchemaAttributeEnumConstraintDependency
from .attribute_kind import SchemaAttributeKindConstraintDependency
from .attribute_length import SchemaAttributLengthConstraintDependency
from .attribute_optional import SchemaAttributeOptionalConstraintDependency
from .attribute_regex import SchemaAttributeRegexConstraintDependency
from .attribute_uniqueness import SchemaAttributeUniqueConstraintDependency
from .generate_profile import SchemaGenerateProfileConstraintDependency
from .inherit_from import SchemaInheritFromConstraintDependency
from .node_attribute import SchemaNodeAttributeAddConstraintDependency
from .node_relationship import SchemaNodeRelationshipAddConstraintDependency
from .relationship_count import SchemaRelationshipCountConstraintDependency
from .relationship_optional import SchemaRelationshipOptionalConstraintDependency
from .uniqueness import SchemaUniquenessConstraintDependency


class AggregatedSchemaConstraintsDependency(DependencyBuilder[AggregatedConstraintChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AggregatedConstraintChecker:
        return AggregatedConstraintChecker(
            constraints=[
                SchemaUniquenessConstraintDependency.build(context=context),
                SchemaGenerateProfileConstraintDependency.build(context=context),
                SchemaInheritFromConstraintDependency.build(context=context),
                SchemaRelationshipOptionalConstraintDependency.build(context=context),
                SchemaRelationshipCountConstraintDependency.build(context=context),
                SchemaAttributeRegexConstraintDependency.build(context=context),
                SchemaAttributeUniqueConstraintDependency.build(context=context),
                SchemaAttributeOptionalConstraintDependency.build(context=context),
                SchemaAttributeChoicesConstraintDependency.build(context=context),
                SchemaAttributeEnumConstraintDependency.build(context=context),
                SchemaAttributLengthConstraintDependency.build(context=context),
                SchemaAttributeKindConstraintDependency.build(context=context),
                SchemaNodeAttributeAddConstraintDependency.build(context=context),
                SchemaNodeRelationshipAddConstraintDependency.build(context=context),
            ],
            db=context.db,
            branch=context.branch,
        )
