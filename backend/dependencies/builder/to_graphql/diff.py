from infrahub.core.to_graphql.base_diff_element import ToGraphQLDiffTranslator
from infrahub.core.to_graphql.diff_summary_element import ToGraphQLDiffSummaryTranslator

from ...interface import DependencyBuilder


class ToGraphQLDiffTranslatorDependency(DependencyBuilder[ToGraphQLDiffTranslator]):
    @classmethod
    def build(cls) -> ToGraphQLDiffTranslator:
        return ToGraphQLDiffTranslator()


class ToGraphQLDiffSummaryTranslatorDependency(DependencyBuilder[ToGraphQLDiffSummaryTranslator]):
    @classmethod
    def build(cls) -> ToGraphQLDiffSummaryTranslator:
        return ToGraphQLDiffSummaryTranslator()
