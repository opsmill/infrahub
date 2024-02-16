from infrahub.core.display_label.renderer import DisplayLabelRenderer

from ..interface import DependencyBuilder
from .attribute_path_parser import AttributePathParserDependency


class DisplayLabelRendererDependency(DependencyBuilder[DisplayLabelRenderer]):
    @classmethod
    def build(cls) -> DisplayLabelRenderer:
        return DisplayLabelRenderer(attribute_path_parser=AttributePathParserDependency.build())
