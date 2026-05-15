from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipDirection
from infrahub.core.node import Node
from infrahub.core.query.node import NodeGetKindQuery
from infrahub.core.query.relationship import RelationshipCountPerNodeQuery
from infrahub.core.schema import MainSchemaTypes
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError

from ..model import RelationshipManager
from .interface import RelationshipManagerConstraintInterface


@dataclass
class NodeToValidate:
    uuid: str
    min_count: int | None = None
    max_count: int | None = None


class RelationshipCountConstraint(RelationshipManagerConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes, node: Node) -> None:  # noqa: ARG002
        branch = await registry.get_branch(db=self.db) if not self.branch else self.branch

        # NOTE adding resolve here because we need to retrieve the real ID
        # but if the validation fails we'll end up with some allocated resources that are not being used
        await relm.resolve(db=self.db)

        # peer_ids_present_local_only:
        #    new relationship, need to check if the schema on the other side has a max_count defined
        # peer_ids_present_database_only:
        #    relationship to be deleted, need to check if the schema on the other side has a min_count defined
        peer_schema = registry.schema.get(name=relm.schema.peer, branch=branch, duplicate=False)
        peer_rels = peer_schema.get_relationships_by_identifier(id=relm.schema.get_identifier())
        update_details = await relm.fetch_relationship_ids(db=self.db, force_refresh=False)
        added_peer_ids = update_details.peer_ids_present_local_only
        removed_peer_ids = update_details.peer_ids_present_database_only

        if peer_rels:
            nodes_to_validate = self._build_validation_targets(
                relm=relm, peer_rels=peer_rels, added_peer_ids=added_peer_ids, removed_peer_ids=removed_peer_ids
            )
        elif isinstance(peer_schema, GenericSchema):
            # The relationship is declared on a concrete subtype rather than on the
            # generic peer itself. Resolve each peer's concrete kind and use its
            # schema to find the applicable cardinality constraint.
            nodes_to_validate = await self._build_validation_targets_from_concrete(
                relm=relm, branch=branch, added_peer_ids=added_peer_ids, removed_peer_ids=removed_peer_ids
            )
        else:
            return

        if not nodes_to_validate:
            return

        query = await RelationshipCountPerNodeQuery.init(
            db=self.db,
            node_ids=[n.uuid for n in nodes_to_validate],
            identifier=relm.schema.identifier,
            direction=relm.schema.direction.neighbor_direction,
            branch=branch,
        )
        await query.execute(db=self.db)
        count_per_peer = await query.get_count_per_peer()

        # Need to adjust the number based on what we will add / remove
        #  +1 for max_count
        #  -1 for min_count
        for node_to_validate in nodes_to_validate:
            if node_to_validate.max_count and count_per_peer[node_to_validate.uuid] + 1 > node_to_validate.max_count:
                raise ValidationError(
                    f"Node {node_to_validate.uuid} has {count_per_peer[node_to_validate.uuid] + 1} peers "
                    f"for {relm.schema.identifier}, maximum of {node_to_validate.max_count} allowed",
                )
            if node_to_validate.min_count and count_per_peer[node_to_validate.uuid] - 1 < node_to_validate.min_count:
                raise ValidationError(
                    f"Node {node_to_validate.uuid} has {count_per_peer[node_to_validate.uuid] - 1} peers "
                    f"for {relm.schema.identifier}, no fewer than {node_to_validate.min_count} allowed",
                )

    def _build_validation_targets(
        self,
        relm: RelationshipManager,
        peer_rels: list[RelationshipSchema],
        added_peer_ids: Iterable[str],
        removed_peer_ids: Iterable[str],
    ) -> list[NodeToValidate]:
        """Build validation targets when the peer schema directly declares the relevant
        relationships. The same ``peer_rels`` apply to every changed peer."""
        targets: list[NodeToValidate] = []
        for peer_id in added_peer_ids:
            targets.extend(self._targets_for_added(peer_id=peer_id, peer_rels=peer_rels, relm=relm))
        for peer_id in removed_peer_ids:
            targets.extend(self._targets_for_removed(peer_id=peer_id, peer_rels=peer_rels, relm=relm))
        return targets

    async def _build_validation_targets_from_concrete(
        self,
        relm: RelationshipManager,
        branch: Branch,
        added_peer_ids: Iterable[str],
        removed_peer_ids: Iterable[str],
    ) -> list[NodeToValidate]:
        """Build validation targets when the declared peer is a generic that does not
        carry the relationship. Each peer's concrete kind is resolved from the database,
        and the applicable ``peer_rels`` may differ between peers (e.g. one subtype
        carries cardinality=one while a sibling carries cardinality=many)."""
        all_changed = [*added_peer_ids, *removed_peer_ids]
        if not all_changed:
            return []

        kind_query = await NodeGetKindQuery.init(db=self.db, ids=all_changed, branch=branch)
        await kind_query.execute(db=self.db)
        kind_per_peer = await kind_query.get_node_kind_map()

        rels_by_kind: dict[str, list[RelationshipSchema]] = {}
        identifier = relm.schema.get_identifier()

        def rels_for(peer_id: str) -> list[RelationshipSchema]:
            kind = kind_per_peer.get(peer_id)
            if kind is None:
                return []
            if kind not in rels_by_kind:
                concrete_schema = registry.schema.get(name=kind, branch=branch, duplicate=False)
                rels_by_kind[kind] = concrete_schema.get_relationships_by_identifier(id=identifier)
            return rels_by_kind[kind]

        targets: list[NodeToValidate] = []
        for peer_id in added_peer_ids:
            targets.extend(self._targets_for_added(peer_id=peer_id, peer_rels=rels_for(peer_id), relm=relm))
        for peer_id in removed_peer_ids:
            targets.extend(self._targets_for_removed(peer_id=peer_id, peer_rels=rels_for(peer_id), relm=relm))
        return targets

    @staticmethod
    def _targets_for_added(
        peer_id: str, peer_rels: list[RelationshipSchema], relm: RelationshipManager
    ) -> Iterator[NodeToValidate]:
        """Yield max_count targets for a peer that is being added."""
        for peer_rel in peer_rels:
            if not _direction_is_compatible(relm=relm, peer_rel=peer_rel):
                continue
            if peer_rel.max_count:
                yield NodeToValidate(uuid=peer_id, max_count=peer_rel.max_count)

    @staticmethod
    def _targets_for_removed(
        peer_id: str, peer_rels: list[RelationshipSchema], relm: RelationshipManager
    ) -> Iterator[NodeToValidate]:
        """Yield min_count targets for a peer that is being removed."""
        for peer_rel in peer_rels:
            if not _direction_is_compatible(relm=relm, peer_rel=peer_rel):
                continue
            if peer_rel.min_count:
                yield NodeToValidate(uuid=peer_id, min_count=peer_rel.min_count)


def _direction_is_compatible(relm: RelationshipManager, peer_rel: RelationshipSchema) -> bool:
    # A directional relationship and its peer cannot both face the same way
    # (only bidirectional pairs can share a direction).
    return relm.schema.direction != peer_rel.direction or peer_rel.direction == RelationshipDirection.BIDIR
