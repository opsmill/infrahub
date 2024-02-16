from infrahub.core.to_graphql.relationship import ToGraphQLRelationshipTranslator

from ...interface import DependencyBuilder


class ToGraphQLRelationshipTranslatorDependency(DependencyBuilder[ToGraphQLRelationshipTranslator]):
    @classmethod
    def build(cls) -> ToGraphQLRelationshipTranslator:
        return ToGraphQLRelationshipTranslator()
