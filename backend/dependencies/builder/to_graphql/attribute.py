from infrahub.core.to_graphql.attribute import ToGraphQLAttributeTranslator

from ...interface import DependencyBuilder


class ToGraphQLAttributeTranslatorDependency(DependencyBuilder[ToGraphQLAttributeTranslator]):
    @classmethod
    def build(cls) -> ToGraphQLAttributeTranslator:
        return ToGraphQLAttributeTranslator()
