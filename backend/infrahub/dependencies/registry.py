from .builder.constraint.grouped.node_runner import NodeConstraintRunnerDependency
from .builder.constraint.node.uniqueness import NodeUniquenessConstraintDependency
from .builder.constraint.relationship_manager.count import RelationshipCountConstraintDependency
from .builder.constraint.schema.aggregated import AggregatedSchemaConstraintsDependency
from .builder.constraint.schema.attribute_regex import SchemaAttributeRegexConstraintDependency
from .builder.constraint.schema.attribute_uniqueness import SchemaAttributeUniqueConstraintDependency
from .builder.constraint.schema.relationship_optional import SchemaRelationshipOptionalConstraintDependency
from .builder.constraint.schema.uniqueness import SchemaUniquenessConstraintDependency
from .component.registry import ComponentDependencyRegistry


def build_component_registry() -> ComponentDependencyRegistry:
    component_registry = ComponentDependencyRegistry.get_registry()
    component_registry.track_dependency(AggregatedSchemaConstraintsDependency)
    component_registry.track_dependency(SchemaAttributeRegexConstraintDependency)
    component_registry.track_dependency(SchemaAttributeUniqueConstraintDependency)
    component_registry.track_dependency(SchemaRelationshipOptionalConstraintDependency)
    component_registry.track_dependency(SchemaUniquenessConstraintDependency)
    component_registry.track_dependency(NodeUniquenessConstraintDependency)
    component_registry.track_dependency(RelationshipCountConstraintDependency)
    component_registry.track_dependency(NodeConstraintRunnerDependency)
    return component_registry


def get_component_registry() -> ComponentDependencyRegistry:
    return ComponentDependencyRegistry.get_registry()
