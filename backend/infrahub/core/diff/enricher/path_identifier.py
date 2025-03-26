from infrahub.core.constants import PathType
from infrahub.core.path import DataPath
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

from ..model.path import CalculatedDiffs, EnrichedDiffRoot
from .interface import DiffEnricherInterface

log = get_logger()


class DiffPathIdentifierEnricher(DiffEnricherInterface):
    """Add path identifiers to every element in the diff"""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db
        self._diff_branch_name: str | None = None

    @property
    def diff_branch_name(self) -> str:
        if not self._diff_branch_name:
            raise RuntimeError("diff_branch_name not set")
        return self._diff_branch_name

    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None:  # noqa: ARG002
        self._diff_branch_name = enriched_diff_root.diff_branch_name
        for node in enriched_diff_root.nodes:
            node_path = DataPath(
                branch=enriched_diff_root.diff_branch_name,
                path_type=PathType.NODE,
                node_id=node.uuid,
                kind=node.kind,
            )
            node.path_identifier = node_path.get_path()
            for attribute in node.attributes:
                attribute_path = DataPath(
                    branch=enriched_diff_root.diff_branch_name,
                    path_type=PathType.ATTRIBUTE,
                    node_id=node.uuid,
                    kind=node.kind,
                    field_name=attribute.name,
                )
                attribute.path_identifier = attribute_path.get_path()
                for attribute_property in attribute.properties:
                    property_path = attribute_path.model_copy()
                    property_path.property_name = attribute_property.property_type.value
                    attribute_property.path_identifier = property_path.get_path()
            if not node.relationships:
                continue
            for relationship in node.relationships:
                path_type = PathType.from_relationship(relationship.cardinality)
                relationship_path = DataPath(
                    branch=enriched_diff_root.diff_branch_name,
                    path_type=path_type,
                    node_id=node.uuid,
                    kind=node.kind,
                    field_name=relationship.name,
                )
                relationship.path_identifier = relationship_path.get_path()
                for relationship_element in relationship.relationships:
                    relationship_element_path = relationship_path.model_copy()
                    relationship_element_path.peer_id = relationship_element.peer_id
                    relationship_element.path_identifier = relationship_element_path.get_path(with_peer=False)
                    for relationship_property in relationship_element.properties:
                        relationship_property_path = relationship_element_path.model_copy()
                        relationship_property_path.property_name = relationship_property.property_type.value
                        relationship_property.path_identifier = relationship_property_path.get_path(with_peer=False)
        log.info("Path identifier diff enrichment complete.")
