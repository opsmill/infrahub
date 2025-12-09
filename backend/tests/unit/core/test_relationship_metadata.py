from dataclasses import dataclass

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


@dataclass
class RelationshipMetadata:
    peer_id: str
    created_time_range: tuple[Timestamp, Timestamp]
    updated_time_range: tuple[Timestamp, Timestamp]
    updated_by: str
    is_protected: bool


class TestRelationshipMetadata:
    def setup_method(self):
        self.person_id = None
        self.black_tag_id = None
        self.red_tag_id = None
        self.blue_tag_id = None
        self.person_schema = None
        self.before_create = None
        self.after_create = None

    def _validate_rel_metadata(
        self,
        rel: Relationship,
        update_time_range: tuple[Timestamp, Timestamp],
        updated_by: str,
        source_id: str | None,
        owner_id: str | None,
    ) -> None:
        assert self.before_create < rel._get_created_at() < self.after_create
        assert rel._get_created_by() == SYSTEM_USER_ID
        assert update_time_range[0] < rel._get_updated_at() < update_time_range[1]
        assert rel._get_updated_by() == updated_by
        assert rel.source_id == source_id
        assert rel.owner_id == owner_id

    async def _get_primary_tag_rel(self, db: InfrahubDatabase, branch: Branch) -> Relationship:
        primary_tag_rels = await NodeManager.query_peers(
            db=db,
            branch=branch,
            ids=[self.person_id],
            source_kind="TestPerson",
            schema=self.person_schema.get_relationship(name="primary_tag"),
            filters={},
            include_metadata=MetadataOptions.USER_TIMESTAMPS
            | MetadataOptions.LINKED_NODES
            | MetadataOptions.IS_PROTECTED,
        )
        return primary_tag_rels[0]

    async def _get_tags_rels(self, db: InfrahubDatabase, branch: Branch) -> dict[str, Relationship]:
        relationships = await NodeManager.query_peers(
            db=db,
            branch=branch,
            ids=[self.person_id],
            source_kind="TestPerson",
            schema=self.person_schema.get_relationship(name="tags"),
            filters={},
            include_metadata=MetadataOptions.USER_TIMESTAMPS
            | MetadataOptions.LINKED_NODES
            | MetadataOptions.IS_PROTECTED,
        )
        return {rel.get_peer_id(): rel for rel in relationships}

    async def _validate_node_metadata(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        node_id: str,
        update_time_range: tuple[Timestamp, Timestamp],
        updated_by: str,
    ) -> None:
        """Validate Node-level _get_updated_at and _get_updated_by metadata."""
        node = await NodeManager.get_one(
            db=db, branch=branch, id=node_id, include_metadata=MetadataOptions.USER_TIMESTAMPS
        )
        assert update_time_range[0] < node._get_updated_at() < update_time_range[1]
        assert node._get_updated_by() == updated_by

    async def _validate_relationship_metadata(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        create_time_range: tuple[Timestamp, Timestamp],
        update_time_range: tuple[Timestamp, Timestamp],
        updated_by: str,
        source_id: str | None,
        owner_id: str | None,
    ) -> None:
        # Validate primary_tag relationship metadata
        updated_primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=branch)
        self._validate_rel_metadata(
            updated_primary_tag_rel,
            update_time_range,
            updated_by,
            source_id,
            owner_id,
        )
        # Validate tags relationships metadata
        updated_tags_rels_map = await self._get_tags_rels(db=db, branch=branch)
        assert len(updated_tags_rels_map) == 2
        # Find the black and red tag relationships
        updated_black_tag_rel = updated_tags_rels_map[self.black_tag_id]
        updated_red_tag_rel = updated_tags_rels_map[self.red_tag_id]
        # validate black tag updates
        self._validate_rel_metadata(
            updated_black_tag_rel,
            update_time_range,
            updated_by,
            source_id,
            owner_id,
        )
        # validate red tag has no updates
        self._validate_rel_metadata(
            updated_red_tag_rel,
            create_time_range,
            SYSTEM_USER_ID,
            None,
            None,
        )

        # validate with get_many as well
        person = await NodeManager.get_one(
            db=db,
            branch=branch,
            id=self.person_id,
            prefetch_relationships=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        updated_primary_tag_rel = await person.primary_tag.get(db=db)
        self._validate_rel_metadata(
            updated_primary_tag_rel,
            update_time_range,
            updated_by,
            # get_many does not support source and owner on rels
            None,
            None,
        )
        # Validate tags relationships metadata
        updated_tags_rels = await person.tags.get(db=db)
        assert len(updated_tags_rels) == 2
        # Find the black and red tag relationships
        updated_black_tag_rel = [r for r in updated_tags_rels if r.get_peer_id() == self.black_tag_id][0]
        updated_red_tag_rel = [r for r in updated_tags_rels if r.get_peer_id() == self.red_tag_id][0]
        # validate black tag updates
        self._validate_rel_metadata(
            updated_black_tag_rel,
            update_time_range,
            updated_by,
            # get_many does not support source and owner on rels
            None,
            None,
        )
        # validate red tag has no updates
        self._validate_rel_metadata(
            updated_red_tag_rel,
            create_time_range,
            SYSTEM_USER_ID,
            None,
            None,
        )

    async def test_relationship_properties_and_metadata_on_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        tag_blue_main: Node,
        tag_red_main: Node,
        tag_black_main: Node,
        person_jack_main: Node,
        first_account: Node,
        second_account: Node,
    ) -> None:
        """Test source and owner properties and metadata on relationships for both cardinality-one and cardinality-many."""
        self.person_schema = registry.schema.get(name="TestPerson")
        self.black_tag_id = tag_black_main.id
        self.red_tag_id = tag_red_main.id

        # Create a person with both primary_tag (cardinality-one) and tags (cardinality-many) relationships on the default branch
        person = await Node.init(db=db, schema=self.person_schema)
        await person.new(
            db=db, firstname="Jake", lastname="Russell", primary_tag=tag_blue_main, tags=[tag_red_main, tag_black_main]
        )
        self.before_create = Timestamp()
        await person.save(db=db)
        self.after_create = Timestamp()
        self.person_id = person.id
        # validate initial metadata for primary_tag
        primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=default_branch)
        self._validate_rel_metadata(
            primary_tag_rel, (self.before_create, self.after_create), SYSTEM_USER_ID, None, None
        )
        # validate initial metadata for tags
        tags_rels_map = await self._get_tags_rels(db=db, branch=default_branch)
        assert len(tags_rels_map) == 2
        for tag_rel in tags_rels_map.values():
            self._validate_rel_metadata(tag_rel, (self.before_create, self.after_create), SYSTEM_USER_ID, None, None)
        # validate initial node-level metadata
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(self.before_create, self.after_create),
            updated_by=SYSTEM_USER_ID,
        )

        # Set the source and owner properties on both relationships on the default branch
        fresh_person = await NodeManager.get_one(db=db, branch=default_branch, id=self.person_id)
        primary_tag_rel = await fresh_person.primary_tag.get(db=db)
        primary_tag_rel.set_source(first_account)
        primary_tag_rel.set_owner(second_account)
        tags_rels = await fresh_person.tags.get_relationships(db=db)
        for tag_rel in tags_rels:
            if tag_rel.get_peer_id() == tag_black_main.id:
                tag_rel.set_source(first_account)
                tag_rel.set_owner(second_account)
        before_first_update = Timestamp()
        await fresh_person.save(db=db, user_id="first-update")
        after_first_update = Timestamp()
        await self._validate_relationship_metadata(
            db=db,
            branch=default_branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_first_update, after_first_update),
            updated_by="first-update",
            source_id=first_account.id,
            owner_id=second_account.id,
        )
        # validate node-level metadata after first update
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(before_first_update, after_first_update),
            updated_by="first-update",
        )

        branch = await create_branch(db=db, branch_name="branch2")

        # update the source and owner properties on both relationships on the default branch
        fresh_person = await NodeManager.get_one(db=db, branch=default_branch, id=self.person_id)
        primary_tag_rel = await fresh_person.primary_tag.get(db=db)
        primary_tag_rel.set_source(second_account)
        primary_tag_rel.set_owner(first_account)
        tags_rels = await fresh_person.tags.get_relationships(db=db)
        for tag_rel in tags_rels:
            if tag_rel.get_peer_id() == tag_black_main.id:
                tag_rel.set_source(second_account)
                tag_rel.set_owner(first_account)
        before_update = Timestamp()
        await fresh_person.save(db=db, user_id="second-update")
        after_update = Timestamp()
        await self._validate_relationship_metadata(
            db=db,
            branch=default_branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_update, after_update),
            updated_by="second-update",
            source_id=second_account.id,
            owner_id=first_account.id,
        )
        # validate node-level metadata after second update on default branch
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(before_update, after_update),
            updated_by="second-update",
        )
        # validate that properties and metadata on branch remain the same
        await self._validate_relationship_metadata(
            db=db,
            branch=branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_first_update, after_first_update),
            updated_by="first-update",
            source_id=first_account.id,
            owner_id=second_account.id,
        )
        # validate node-level metadata on branch remains the same as first update
        await self._validate_node_metadata(
            db=db,
            branch=branch,
            node_id=self.person_id,
            update_time_range=(before_first_update, after_first_update),
            updated_by="first-update",
        )

        # Update the source and owner properties on the branch
        fresh_person_branch = await NodeManager.get_one(db=db, branch=branch, id=self.person_id)
        primary_tag_rel_branch = await fresh_person_branch.primary_tag.get(db=db)
        primary_tag_rel_branch.set_source(second_account)
        primary_tag_rel_branch.set_owner(first_account)
        tags_rels_branch = await fresh_person_branch.tags.get_relationships(db=db)
        for tag_rel in tags_rels_branch:
            if tag_rel.get_peer_id() == tag_black_main.id:
                tag_rel.set_source(second_account)
                tag_rel.set_owner(first_account)
        before_branch_update = Timestamp()
        await fresh_person_branch.save(db=db, user_id="first-branch-update")
        after_branch_update = Timestamp()
        # Validate that default_branch keeps the same metadata
        await self._validate_relationship_metadata(
            db=db,
            branch=default_branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_update, after_update),
            updated_by="second-update",
            source_id=second_account.id,
            owner_id=first_account.id,
        )
        # validate node-level metadata on default branch remains unchanged
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(before_update, after_update),
            updated_by="second-update",
        )
        # Validate that branch now has the updated source and owner and metadata
        await self._validate_relationship_metadata(
            db=db,
            branch=branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_branch_update, after_branch_update),
            updated_by="first-branch-update",
            source_id=second_account.id,
            owner_id=first_account.id,
        )
        # validate node-level metadata on branch reflects the branch update
        await self._validate_node_metadata(
            db=db,
            branch=branch,
            node_id=self.person_id,
            update_time_range=(before_branch_update, after_branch_update),
            updated_by="first-branch-update",
        )

        # clear the source and owner properties on both relationships on the default branch
        fresh_person = await NodeManager.get_one(db=db, branch=default_branch, id=self.person_id)
        primary_tag_rel = await fresh_person.primary_tag.get(db=db)
        primary_tag_rel.clear_source()
        primary_tag_rel.clear_owner()
        tags_rels = await fresh_person.tags.get_relationships(db=db)
        for tag_rel in tags_rels:
            if tag_rel.get_peer_id() == tag_black_main.id:
                tag_rel.clear_source()
                tag_rel.clear_owner()
        before_update = Timestamp()
        await fresh_person.save(db=db, user_id="third-update")
        after_update = Timestamp()
        await self._validate_relationship_metadata(
            db=db,
            branch=default_branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_update, after_update),
            updated_by="third-update",
            source_id=None,
            owner_id=None,
        )
        # validate node-level metadata on default branch after third update
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(before_update, after_update),
            updated_by="third-update",
        )
        # Validate that branch keeps the same metadata
        await self._validate_relationship_metadata(
            db=db,
            branch=branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_branch_update, after_branch_update),
            updated_by="first-branch-update",
            source_id=second_account.id,
            owner_id=first_account.id,
        )
        # validate node-level metadata on branch remains unchanged
        await self._validate_node_metadata(
            db=db,
            branch=branch,
            node_id=self.person_id,
            update_time_range=(before_branch_update, after_branch_update),
            updated_by="first-branch-update",
        )

        # clear the source and owner on the branch
        fresh_person_branch = await NodeManager.get_one(db=db, branch=branch, id=self.person_id)
        primary_tag_rel_branch = await fresh_person_branch.primary_tag.get(db=db)
        primary_tag_rel_branch.clear_source()
        primary_tag_rel_branch.clear_owner()
        tags_rels_branch = await fresh_person_branch.tags.get_relationships(db=db)
        for tag_rel in tags_rels_branch:
            if tag_rel.get_peer_id() == tag_black_main.id:
                tag_rel.clear_source()
                tag_rel.clear_owner()
        before_branch_update_2 = Timestamp()
        await fresh_person_branch.save(db=db, user_id="second-branch-update")
        after_branch_update_2 = Timestamp()
        # validate that source and owner are cleared on the branch
        await self._validate_relationship_metadata(
            db=db,
            branch=branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_branch_update_2, after_branch_update_2),
            updated_by="second-branch-update",
            source_id=None,
            owner_id=None,
        )
        # validate node-level metadata on branch after second branch update
        await self._validate_node_metadata(
            db=db,
            branch=branch,
            node_id=self.person_id,
            update_time_range=(before_branch_update_2, after_branch_update_2),
            updated_by="second-branch-update",
        )
        # validate that default_branch still has cleared source and owner from before
        await self._validate_relationship_metadata(
            db=db,
            branch=default_branch,
            create_time_range=(self.before_create, self.after_create),
            update_time_range=(before_update, after_update),
            updated_by="third-update",
            source_id=None,
            owner_id=None,
        )
        # validate node-level metadata on default branch remains unchanged
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(before_update, after_update),
            updated_by="third-update",
        )

    def _validate_rel_metadata_peer_and_protected(
        self,
        rels: list[Relationship],
        relationship_metadatas: list[RelationshipMetadata],
    ) -> None:
        assert len(rels) == len(relationship_metadatas), (
            f"Number of relationships ({len(rels)}) must match number of metadata objects ({len(relationship_metadatas)})"
        )
        # Create a mapping of peer_id to metadata for easier lookup
        metadata_by_peer_id = {meta.peer_id: meta for meta in relationship_metadatas}
        # Validate each relationship against its corresponding metadata
        for rel in rels:
            peer_id = rel.get_peer_id()
            assert peer_id in metadata_by_peer_id, f"Metadata not found for peer_id: {peer_id}"
            metadata = metadata_by_peer_id[peer_id]
            assert metadata.created_time_range[0] < rel._get_created_at() < metadata.created_time_range[1]
            assert metadata.updated_time_range[0] < rel._get_updated_at() < metadata.updated_time_range[1]
            assert rel._get_updated_by() == metadata.updated_by
            assert rel.is_protected == metadata.is_protected

    async def test_relationship_peer_and_is_protected_metadata_on_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        tag_blue_main: Node,
        tag_red_main: Node,
        tag_black_main: Node,
        person_jack_main: Node,
    ) -> None:
        """Test peer updates and is_protected metadata on relationships for both cardinality-one and cardinality-many."""
        self.person_schema = registry.schema.get(name="TestPerson")
        self.black_tag_id = tag_black_main.id
        self.red_tag_id = tag_red_main.id
        self.blue_tag_id = tag_blue_main.id

        # Create a person with both primary_tag (cardinality-one) and tags (cardinality-many) relationships on the default branch
        person = await Node.init(db=db, schema=self.person_schema)
        await person.new(
            db=db, firstname="Jake", lastname="Russell", primary_tag=tag_blue_main, tags=[tag_red_main, tag_black_main]
        )
        self.before_create = Timestamp()
        await person.save(db=db)
        self.after_create = Timestamp()
        self.person_id = person.id
        # validate initial metadata for primary_tag
        primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=default_branch)
        self._validate_rel_metadata_peer_and_protected(
            [primary_tag_rel],
            [
                RelationshipMetadata(
                    peer_id=tag_blue_main.id,
                    created_time_range=(self.before_create, self.after_create),
                    updated_time_range=(self.before_create, self.after_create),
                    updated_by=SYSTEM_USER_ID,
                    is_protected=False,
                )
            ],
        )
        # validate initial metadata for tags
        tags_rels_map = await self._get_tags_rels(db=db, branch=default_branch)
        assert len(tags_rels_map) == 2
        tag_rels = list(tags_rels_map.values())
        tag_metadatas = [
            RelationshipMetadata(
                peer_id=tag_rel.get_peer_id(),
                created_time_range=(self.before_create, self.after_create),
                updated_time_range=(self.before_create, self.after_create),
                updated_by=SYSTEM_USER_ID,
                is_protected=False,
            )
            for tag_rel in tag_rels
        ]
        self._validate_rel_metadata_peer_and_protected(tag_rels, tag_metadatas)
        # validate initial node-level metadata
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(self.before_create, self.after_create),
            updated_by=SYSTEM_USER_ID,
        )

        # Set is_protected on both relationships on the default branch
        fresh_person = await NodeManager.get_one(db=db, branch=default_branch, id=self.person_id)
        primary_tag_rel = await fresh_person.primary_tag.get(db=db)
        primary_tag_rel.is_protected = True
        tags_rels = await fresh_person.tags.get_relationships(db=db)
        for tag_rel in tags_rels:
            if tag_rel.get_peer_id() == tag_black_main.id:
                tag_rel.is_protected = True
        before_first_update = Timestamp()
        await fresh_person.save(db=db, user_id="first-update")
        after_first_update = Timestamp()

        primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=default_branch)
        primary_tag_metadata_main_1 = RelationshipMetadata(
            peer_id=tag_blue_main.id,
            created_time_range=(self.before_create, self.after_create),
            updated_time_range=(before_first_update, after_first_update),
            updated_by="first-update",
            is_protected=True,
        )
        self._validate_rel_metadata_peer_and_protected([primary_tag_rel], [primary_tag_metadata_main_1])

        tags_rels_map = await self._get_tags_rels(db=db, branch=default_branch)
        tags_metadata_main_1 = [
            RelationshipMetadata(
                peer_id=tag_red_main.id,
                created_time_range=(self.before_create, self.after_create),
                updated_time_range=(self.before_create, self.after_create),
                updated_by=SYSTEM_USER_ID,
                is_protected=False,
            ),
            RelationshipMetadata(
                peer_id=tag_black_main.id,
                created_time_range=(self.before_create, self.after_create),
                updated_time_range=(before_first_update, after_first_update),
                updated_by="first-update",
                is_protected=True,
            ),
        ]
        self._validate_rel_metadata_peer_and_protected(list(tags_rels_map.values()), tags_metadata_main_1)
        # validate node-level metadata after first update
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(before_first_update, after_first_update),
            updated_by="first-update",
        )

        branch = await create_branch(db=db, branch_name="branch2")

        # Update the primary_tag relationship to a new peer (set to red tag)
        fresh_person = await NodeManager.get_one(db=db, branch=default_branch, id=self.person_id)
        await fresh_person.primary_tag.update(db=db, data=self.red_tag_id)
        # Remove black tag, add blue tag
        await fresh_person.tags.update(db=db, data=[self.black_tag_id, self.blue_tag_id])
        before_update = Timestamp()
        await fresh_person.save(db=db, user_id="second-update")
        after_update = Timestamp()
        # Validate primary_tag relationship update on default branch
        primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=default_branch)
        assert primary_tag_rel.get_peer_id() == tag_red_main.id
        primary_tag_metadata_main_2 = RelationshipMetadata(
            peer_id=tag_red_main.id,
            created_time_range=(before_update, after_update),
            updated_time_range=(before_update, after_update),
            updated_by="second-update",
            is_protected=False,
        )
        self._validate_rel_metadata_peer_and_protected([primary_tag_rel], [primary_tag_metadata_main_2])
        # Validate tags relationships update on default branch
        tags_rels_map = await self._get_tags_rels(db=db, branch=default_branch)
        assert set(tags_rels_map.keys()) == {tag_black_main.id, tag_blue_main.id}
        tags_metadata_main_2 = [
            RelationshipMetadata(
                peer_id=tag_black_main.id,
                created_time_range=(self.before_create, self.after_create),
                updated_time_range=(before_first_update, after_first_update),
                updated_by="first-update",
                is_protected=True,
            ),
            RelationshipMetadata(
                peer_id=tag_blue_main.id,
                created_time_range=(before_update, after_update),
                updated_time_range=(before_update, after_update),
                updated_by="second-update",
                is_protected=False,
            ),
        ]
        self._validate_rel_metadata_peer_and_protected(list(tags_rels_map.values()), tags_metadata_main_2)
        # validate node-level metadata on default branch after second update
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(before_update, after_update),
            updated_by="second-update",
        )
        # validate primary_tag relationship remains unchanged on branch
        primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=branch)
        self._validate_rel_metadata_peer_and_protected([primary_tag_rel], [primary_tag_metadata_main_1])
        # validate tags relationships remain unchanged on branch
        tags_rels_map = await self._get_tags_rels(db=db, branch=branch)
        self._validate_rel_metadata_peer_and_protected(list(tags_rels_map.values()), tags_metadata_main_1)
        # validate node-level metadata on branch remains unchanged
        await self._validate_node_metadata(
            db=db,
            branch=branch,
            node_id=self.person_id,
            update_time_range=(before_first_update, after_first_update),
            updated_by="first-update",
        )

        # Update is_protected status on the primary_tag relationship and one of the peers in the tags relationship on branch
        fresh_person_branch = await NodeManager.get_one(db=db, branch=branch, id=self.person_id)
        primary_tag_rel_branch = await fresh_person_branch.primary_tag.get(db=db)
        primary_tag_rel_branch.is_protected = False
        tags_rels_branch = await fresh_person_branch.tags.get_relationships(db=db)
        for tag_rel in tags_rels_branch:
            if tag_rel.get_peer_id() == tag_red_main.id:
                tag_rel.is_protected = True
        before_branch_update = Timestamp()
        await fresh_person_branch.save(db=db, user_id="branch-update-1")
        after_branch_update = Timestamp()
        # Validate that the changes are correct on the branch
        primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=branch)
        primary_tag_metadata_branch = RelationshipMetadata(
            peer_id=tag_blue_main.id,
            created_time_range=(self.before_create, self.after_create),
            updated_time_range=(before_branch_update, after_branch_update),
            updated_by="branch-update-1",
            is_protected=False,
        )
        self._validate_rel_metadata_peer_and_protected([primary_tag_rel], [primary_tag_metadata_branch])
        tags_rels_map = await self._get_tags_rels(db=db, branch=branch)
        tags_metadata_branch = [
            RelationshipMetadata(
                peer_id=tag_red_main.id,
                created_time_range=(self.before_create, self.after_create),
                updated_time_range=(before_branch_update, after_branch_update),
                updated_by="branch-update-1",
                is_protected=True,
            ),
            RelationshipMetadata(
                peer_id=tag_black_main.id,
                created_time_range=(self.before_create, self.after_create),
                updated_time_range=(before_first_update, after_first_update),
                updated_by="first-update",
                is_protected=True,
            ),
        ]
        self._validate_rel_metadata_peer_and_protected(list(tags_rels_map.values()), tags_metadata_branch)
        # validate node-level metadata on branch after branch update
        await self._validate_node_metadata(
            db=db,
            branch=branch,
            node_id=self.person_id,
            update_time_range=(before_branch_update, after_branch_update),
            updated_by="branch-update-1",
        )
        # Validate that no changes were made on the default branch
        primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=default_branch)
        self._validate_rel_metadata_peer_and_protected([primary_tag_rel], [primary_tag_metadata_main_2])
        tags_rels_map = await self._get_tags_rels(db=db, branch=default_branch)
        self._validate_rel_metadata_peer_and_protected(list(tags_rels_map.values()), tags_metadata_main_2)
        # validate node-level metadata on default branch remains unchanged
        await self._validate_node_metadata(
            db=db,
            branch=default_branch,
            node_id=self.person_id,
            update_time_range=(before_update, after_update),
            updated_by="second-update",
        )
