from typing import List

import ujson

from infrahub_sdk.node import InfrahubNode

from ..model import SerializedAttribute, SerializedNode, SerializedRelationship
from .interface import ExporterInterface


class JSONExporter(ExporterInterface):
    async def export(self, nodes: List[InfrahubNode]) -> str:
        serialized = []
        for n in nodes:
            attributes = [
                SerializedAttribute(name=name, value=value) for name, value in (await n.get_attributes()).items()
            ]
            relationships = [
                SerializedRelationship(name=name, linked_ids=linked_ids)
                for name, linked_ids in (await n.get_relationships()).items()
            ]
            serialized.append(
                SerializedNode(
                    id=n.id,
                    display_label=n.display_label,
                    namespace=n.get_namespace(),
                    name=n.get_name(),
                    attributes=attributes,
                    relationships=relationships,
                )
            )
        return ujson.dumps([s.dict() for s in serialized])
