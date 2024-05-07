from .builder.constraint.grouped.node_runner import NodeConstraintRunnerDependency
from .builder.constraint.node.grouped_uniqueness import NodeGroupedUniquenessConstraintDependency
from .builder.constraint.node.uniqueness import NodeAttributeUniquenessConstraintDependency
from .builder.constraint.relationship_manager.count import RelationshipCountConstraintDependency
from .builder.constraint.schema.aggregated import AggregatedSchemaConstraintsDependency
from .builder.constraint.schema.attribute_regex import SchemaAttributeRegexConstraintDependency
from .builder.constraint.schema.attribute_uniqueness import SchemaAttributeUniqueConstraintDependency
from .builder.constraint.schema.relationship_optional import SchemaRelationshipOptionalConstraintDependency
from .builder.constraint.schema.uniqueness import SchemaUniquenessConstraintDependency
from .builder.node.delete_validator import NodeDeleteValidatorDependency
from .component.registry import ComponentDependencyRegistry


def build_component_registry() -> ComponentDependencyRegistry:
    component_registry = ComponentDependencyRegistry.get_registry()
    component_registry.track_dependency(AggregatedSchemaConstraintsDependency)
    component_registry.track_dependency(SchemaAttributeRegexConstraintDependency)
    component_registry.track_dependency(SchemaAttributeUniqueConstraintDependency)
    component_registry.track_dependency(SchemaRelationshipOptionalConstraintDependency)
    component_registry.track_dependency(SchemaUniquenessConstraintDependency)
    component_registry.track_dependency(NodeAttributeUniquenessConstraintDependency)
    component_registry.track_dependency(NodeGroupedUniquenessConstraintDependency)
    component_registry.track_dependency(RelationshipCountConstraintDependency)
    component_registry.track_dependency(NodeConstraintRunnerDependency)
    component_registry.track_dependency(NodeDeleteValidatorDependency)
    return component_registry


def get_component_registry() -> ComponentDependencyRegistry:
    return ComponentDependencyRegistry.get_registry()
