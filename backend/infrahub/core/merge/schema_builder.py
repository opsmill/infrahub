from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.models import HashableModelDiff
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes, RelationshipSchema
    from infrahub.core.schema.schema_branch import SchemaBranch

ELEMENT_COLLECTIONS = ("attributes", "relationships")


class MergedSchemaBuilder:
    """Build the schema a merge or a rebase produces, moving only what the source branch changed.

    Overlaying a whole branch schema onto the destination writes back every value the branch
    inherited when it forked, reverting anything the destination has changed since. Only the
    properties the branch itself changed may move.
    """

    def build(
        self,
        *,
        ancestor: SchemaBranch,
        source: SchemaBranch,
        destination: SchemaBranch,
        keep_destination_property_map: dict[str, set[str]] | None = None,
    ) -> SchemaBranch:
        """Overlay the source branch's own schema changes onto the destination schema.

        Args:
            ancestor: The destination's schema at the point the source branch forked. What the
                source changed is measured against this, not against the destination's current state.
            source: The source branch's schema.
            destination: The schema to build on top of.
            keep_destination_property_map: Properties with conflicts resolved in favor of the
                destination, so the merge will not write the source's value and neither may this
                builder. Maps a schema element's ``id`` — the uuid of its ``SchemaNode``,
                ``SchemaAttribute`` or ``SchemaRelationship`` vertex — to the property names to leave
                alone.

        """
        keep_destination = keep_destination_property_map or {}
        candidate = destination.duplicate()
        source_delta = ancestor.diff(other=source)

        for kind in source_delta.added:
            candidate.set(name=kind, schema=source.get(name=kind))

        for kind in source_delta.removed:
            if candidate.has(name=kind):
                candidate.delete(name=kind)

        candidate_names_by_id = self._names_by_id(candidate)

        for kind, node_diff in source_delta.changed.items():
            if not source.has(name=kind):
                continue
            source_node = source.get(name=kind, duplicate=False)
            candidate_name = candidate_names_by_id.get(source_node.id) if source_node.id else None
            if candidate_name is None and candidate.has(name=kind):
                candidate_name = kind
            if candidate_name is None:
                continue

            node = candidate.get(name=candidate_name)
            self._apply_node_diff(
                node=node,
                source_node=source_node,
                node_diff=node_diff,
                keep_destination=keep_destination,
            )
            if candidate_name != kind:
                candidate.delete(name=candidate_name)
            candidate.set(name=kind, schema=node)

        return candidate

    @staticmethod
    def _names_by_id(schema: SchemaBranch) -> dict[str, str]:
        names_by_id: dict[str, str] = {}
        for name in schema.node_names + schema.generic_names:
            element_id = schema.get(name=name, duplicate=False).id
            if element_id:
                names_by_id[element_id] = name
        return names_by_id

    def _apply_node_diff(
        self,
        node: MainSchemaTypes,
        source_node: MainSchemaTypes,
        node_diff: HashableModelDiff,
        keep_destination: dict[str, set[str]],
    ) -> None:
        for field_name, field_diff in node_diff.changed.items():
            if field_name in ELEMENT_COLLECTIONS and field_diff is not None:
                self._apply_element_diff(
                    node=node,
                    source_node=source_node,
                    collection_name=field_name,
                    element_diff=field_diff,
                    keep_destination=keep_destination,
                )
            elif self._may_move(element_id=node.id, property_name=field_name, keep_destination=keep_destination):
                setattr(node, field_name, getattr(source_node, field_name))

    def _apply_element_diff(
        self,
        node: MainSchemaTypes,
        source_node: MainSchemaTypes,
        collection_name: str,
        element_diff: HashableModelDiff,
        keep_destination: dict[str, set[str]],
    ) -> None:
        source_elements = {element.name: element for element in getattr(source_node, collection_name)}

        if element_diff.removed:
            setattr(
                node,
                collection_name,
                [element for element in getattr(node, collection_name) if element.name not in element_diff.removed],
            )

        existing_names = {element.name for element in getattr(node, collection_name)}
        for name in element_diff.added:
            if name in source_elements and name not in existing_names:
                getattr(node, collection_name).append(source_elements[name].duplicate())

        for name, property_diff in element_diff.changed.items():
            source_element = source_elements.get(name)
            if source_element is None or property_diff is None:
                continue
            target_element = self._match_element(
                elements=getattr(node, collection_name), element_id=source_element.id, name=name
            )
            if target_element is None:
                continue
            for property_name in property_diff.changed:
                if self._may_move(
                    element_id=target_element.id, property_name=property_name, keep_destination=keep_destination
                ):
                    setattr(target_element, property_name, getattr(source_element, property_name))

    @staticmethod
    def _match_element(
        elements: list[AttributeSchema | RelationshipSchema], element_id: str | None, name: str
    ) -> AttributeSchema | RelationshipSchema | None:
        if element_id:
            for element in elements:
                if element.id == element_id:
                    return element
        return next((element for element in elements if element.name == name), None)

    def _may_move(self, element_id: str | None, property_name: str, keep_destination: dict[str, set[str]]) -> bool:
        if element_id is None:
            return True
        return property_name not in keep_destination.get(element_id, set())
