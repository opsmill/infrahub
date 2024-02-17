from .builder.constraint.schema.aggregated import AggregatedSchemaConstraintsDependency
from .builder.constraint.schema.attribute_regex import SchemaAttributeRegexConstraintDependency
from .builder.constraint.schema.attribute_uniqueness import SchemaAttributeUniqueConstraintDependency
from .builder.constraint.schema.relationship_optional import SchemaRelationshipOptionalConstraintDependency
from .builder.constraint.schema.uniqueness import SchemaUniquenessConstraintDependency
from .component.registry import ComponentDependencyRegistry


def build_component_registry():
    component_registry = ComponentDependencyRegistry()
    component_registry.track_dependency(AggregatedSchemaConstraintsDependency)
    component_registry.track_dependency(SchemaAttributeRegexConstraintDependency)
    component_registry.track_dependency(SchemaAttributeUniqueConstraintDependency)
    component_registry.track_dependency(SchemaRelationshipOptionalConstraintDependency)
    component_registry.track_dependency(SchemaUniquenessConstraintDependency)

    return component_registry


def get_component_registry():
    return ComponentDependencyRegistry.get_registry()
