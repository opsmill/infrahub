from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


class TestRelationshipMetadata:
    def setup_method(self):
        self.person_id = None
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
            include_metadata=MetadataOptions.USER_TIMESTAMPS | MetadataOptions.LINKED_NODES,
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
            include_metadata=MetadataOptions.USER_TIMESTAMPS | MetadataOptions.LINKED_NODES,
        )
        return {rel.get_peer_id(): rel for rel in relationships}

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
        before_update = Timestamp()
        await fresh_person.save(db=db, user_id="first-update")
        after_update = Timestamp()

        # Validate primary_tag relationship metadata
        updated_primary_tag_rel = await self._get_primary_tag_rel(db=db, branch=default_branch)
        self._validate_rel_metadata(
            updated_primary_tag_rel,
            (before_update, after_update),
            "first-update",
            first_account.id,
            second_account.id,
        )

        # Validate tags relationships metadata
        updated_tags_rels_map = await self._get_tags_rels(db=db, branch=default_branch)
        assert len(updated_tags_rels_map) == 2

        # Find the black and red tag relationships
        updated_black_tag_rel = updated_tags_rels_map[tag_black_main.id]
        updated_red_tag_rel = updated_tags_rels_map[tag_red_main.id]

        # Black tag should have source and owner set
        self._validate_rel_metadata(
            updated_black_tag_rel,
            (before_update, after_update),
            "first-update",
            first_account.id,
            second_account.id,
        )

        # Red tag should still have None for source and owner (wasn't modified)
        self._validate_rel_metadata(
            updated_red_tag_rel,
            (self.before_create, self.after_create),
            SYSTEM_USER_ID,
            None,
            None,
        )
