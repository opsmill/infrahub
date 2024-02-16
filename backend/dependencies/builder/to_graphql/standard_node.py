from infrahub.core.to_graphql.standard_node import ToGraphQLStandardNodeTranslator

from ...interface import DependencyBuilder


class ToGraphQLStandardNodeTranslatorDependency(DependencyBuilder[ToGraphQLStandardNodeTranslator]):
    @classmethod
    def build(cls) -> ToGraphQLStandardNodeTranslator:
        return ToGraphQLStandardNodeTranslator()
