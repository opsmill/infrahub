from infrahub.core.attribute_path.parser import AttributePathParser

from ..interface import DependencyBuilder


class AttributePathParserDependency(DependencyBuilder[AttributePathParser]):
    @classmethod
    def build(cls) -> AttributePathParser:
        return AttributePathParser()
