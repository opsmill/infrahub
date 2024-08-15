from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.diff import ModifiedPathType

from ..model.path import CalculatedDiffs, EnrichedDiffProperty, EnrichedDiffRoot
from .interface import DiffEnricherInterface


class DiffPathIdentifierEnricher(DiffEnricherInterface):
    """Add path identifiers to every element in the diff"""

    def __init__(self) -> None:
        self._diff_branch_name: str | None = None

    @property
    def diff_branch_name(self) -> str:
        if not self._diff_branch_name:
            raise RuntimeError("diff_branch_name not set")
        return self._diff_branch_name

    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None:
        self._diff_branch_name = enriched_diff_root.diff_branch_name
        for node in enriched_diff_root.nodes:
            node_path = f"{ModifiedPathType.DATA.value}/{node.uuid}"
            node.path_identifier = node_path
            for attribute in node.attributes:
                attribute_path = f"{node_path}/{attribute.name}"
                attribute.path_identifier = attribute_path
                for attribute_property in attribute.properties:
                    attribute_property_path = self._get_property_path(
                        base_path=attribute_path, diff_property=attribute_property
                    )
                    attribute_property.path_identifier = attribute_property_path
            if not node.relationships:
                continue
            for relationship in node.relationships:
                relationship_path = f"{node_path}/{relationship.name}"
                relationship.path_identifier = relationship_path
                if not relationship.relationships:
                    continue
                for relationship_element in relationship.relationships:
                    relationship_element_path = f"{relationship_path}/{relationship_element.peer_id}"
                    relationship_element.path_identifier = relationship_element_path
                    for relationship_property in relationship_element.properties:
                        relationship_property_path = self._get_property_path(
                            base_path=relationship_element_path, diff_property=relationship_property
                        )
                        relationship_property.path_identifier = relationship_property_path

    def _get_property_path(self, base_path: str, diff_property: EnrichedDiffProperty) -> str:
        if diff_property.property_type is DatabaseEdgeType.HAS_VALUE:
            return f"{base_path}/value"
        return f"{base_path}/property/{diff_property.property_type.value}"
