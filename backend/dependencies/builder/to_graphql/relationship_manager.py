from infrahub.core.to_graphql.relationship_manager import ToGraphQLRelationshipManagerTranslator

from ...interface import DependencyBuilder


class ToGraphQLRelationshipManagerTranslatorDependency(DependencyBuilder[ToGraphQLRelationshipManagerTranslator]):
    @classmethod
    def build(cls) -> ToGraphQLRelationshipManagerTranslator:
        return ToGraphQLRelationshipManagerTranslator()
