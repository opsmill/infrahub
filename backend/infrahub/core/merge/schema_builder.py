from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema.basenode_schema import INHERITED
from infrahub.core.schema.derived_kinds import get_object_template_kind, get_profile_kind

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
                self._carry_generated_kinds(candidate=candidate, source=source, kind=kind)
            candidate.set(name=kind, schema=node)

        return candidate

    @staticmethod
    def _carry_generated_kinds(candidate: SchemaBranch, source: SchemaBranch, kind: str) -> None:
        """Take the profile and template the source generated for a renamed kind.

        Deleting the kind under its old name takes its generated schemas with it, and nothing
        regenerates them here.
        """
        for generated_kind in (get_profile_kind(node_kind=kind), get_object_template_kind(node_kind=kind)):
            if source.has(name=generated_kind):
                candidate.set(name=generated_kind, schema=source.get(name=generated_kind))

    @staticmethod
    def _names_by_id(schema: SchemaBranch) -> dict[str, str]:
        """Map each kind's id to the name it currently goes by.

        Built from the same kind map the diff is built from, so the two cannot disagree about which
        kinds are in play.
        """
        return {
            kind_id: name
            for name, kind_id in schema.get_all_kind_id_map(nodes_and_generics_only=True).items()
            if kind_id
        }

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

        source_ids_by_name = source_node.get_element_name_id_map(collection_name=collection_name)
        target_names_by_id = {
            element_id: element_name
            for element_name, element_id in node.get_element_name_id_map(collection_name=collection_name).items()
            if element_id and element_id != INHERITED
        }

        for name, property_diff in element_diff.changed.items():
            source_element = source_elements.get(name)
            if source_element is None or property_diff is None:
                continue
            target_element = self._match_element(
                elements=getattr(node, collection_name),
                target_names_by_id=target_names_by_id,
                element_id=source_ids_by_name.get(name),
                name=name,
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
        elements: list[AttributeSchema | RelationshipSchema],
        target_names_by_id: dict[str, str],
        element_id: str | None,
        name: str,
    ) -> AttributeSchema | RelationshipSchema | None:
        target_name = target_names_by_id.get(element_id) if element_id and element_id != INHERITED else None
        return next((element for element in elements if element.name == (target_name or name)), None)

    def _may_move(self, element_id: str | None, property_name: str, keep_destination: dict[str, set[str]]) -> bool:
        if element_id is None:
            return True
        return property_name not in keep_destination.get(element_id, set())
