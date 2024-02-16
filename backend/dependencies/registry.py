from .builder.attribute_path_parser import AttributePathParserDependency
from .builder.display_label_renderer import DisplayLabelRendererDependency
from .builder.to_graphql.aggregated import AggregatedToGraphQLTranslatorsDependency
from .builder.to_graphql.attribute import ToGraphQLAttributeTranslatorDependency
from .builder.to_graphql.node import ToGraphQLNodeTranslatorDependency
from .builder.to_graphql.relationship import ToGraphQLRelationshipTranslatorDependency
from .builder.to_graphql.relationship_manager import ToGraphQLRelationshipManagerTranslatorDependency
from .builder.to_graphql.standard_node import ToGraphQLStandardNodeTranslatorDependency
from .component.registry import ComponentDependencyRegistry

_component_registry = None


def build_component_registry():
    component_registry = ComponentDependencyRegistry()
    component_registry.track_dependency(AttributePathParserDependency)
    component_registry.track_dependency(DisplayLabelRendererDependency)
    component_registry.track_dependency(ToGraphQLAttributeTranslatorDependency)
    component_registry.track_dependency(ToGraphQLNodeTranslatorDependency)
    component_registry.track_dependency(ToGraphQLRelationshipTranslatorDependency)
    component_registry.track_dependency(ToGraphQLRelationshipManagerTranslatorDependency)
    component_registry.track_dependency(ToGraphQLStandardNodeTranslatorDependency)
    component_registry.track_dependency(AggregatedToGraphQLTranslatorsDependency)
    return component_registry


def get_component_registry():
    global _component_registry
    if not _component_registry:
        _component_registry = build_component_registry()
    return _component_registry
