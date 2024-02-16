from infrahub.core.to_graphql.aggregated import AggregatedToGraphQLTranslators

from ...interface import DependencyBuilder
from .attribute import ToGraphQLAttributeTranslatorDependency
from .diff import ToGraphQLDiffSummaryTranslatorDependency, ToGraphQLDiffTranslatorDependency
from .node import ToGraphQLNodeTranslatorDependency
from .relationship import ToGraphQLRelationshipTranslatorDependency
from .relationship_manager import ToGraphQLRelationshipManagerTranslatorDependency
from .standard_node import ToGraphQLStandardNodeTranslatorDependency


class AggregatedToGraphQLTranslatorsDependency(DependencyBuilder[AggregatedToGraphQLTranslators]):
    @classmethod
    def build(cls) -> AggregatedToGraphQLTranslators:
        return AggregatedToGraphQLTranslators(
            translators=[
                ToGraphQLAttributeTranslatorDependency.build(),
                ToGraphQLDiffTranslatorDependency.build(),
                ToGraphQLDiffSummaryTranslatorDependency.build(),
                ToGraphQLNodeTranslatorDependency.build(),
                ToGraphQLRelationshipManagerTranslatorDependency.build(),
                ToGraphQLRelationshipTranslatorDependency.build(),
                ToGraphQLStandardNodeTranslatorDependency.build(),
            ]
        )
