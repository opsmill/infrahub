from infrahub.core.to_graphql.node import ToGraphQLNodeTranslator

from ...interface import DependencyBuilder
from ..display_label_renderer import DisplayLabelRendererDependency


class ToGraphQLNodeTranslatorDependency(DependencyBuilder[ToGraphQLNodeTranslator]):
    @classmethod
    def build(cls) -> ToGraphQLNodeTranslator:
        return ToGraphQLNodeTranslator(display_label_renderer=DisplayLabelRendererDependency.build())
