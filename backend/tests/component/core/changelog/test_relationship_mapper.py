from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.changelog.models import RelationshipCardinalityOneChangelog
from infrahub.core.changelog.relationship_mapper import ChangelogRelationshipMapper
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_add_peer_from_one_cardinality_relationship_records_the_edge_metadata(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """Adding a one-cardinality peer records the edge's is_protected metadata, like a many peer does."""
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    owner = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    dog = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=owner)
    await dog.save(db=db)

    owner_rel_schema = dog_schema.get_relationship(name="owner")
    relationship = Relationship(schema=owner_rel_schema, branch=default_branch, node=dog, source_kind=dog.get_kind())
    await relationship.new(db=db, data=owner)

    mapper = ChangelogRelationshipMapper(schema=owner_rel_schema)
    mapper.add_peer_from_relationship(relationship=relationship)

    changelog = mapper.changelog
    assert isinstance(changelog, RelationshipCardinalityOneChangelog)
    assert changelog.peer_id == owner.id
    assert "is_protected" in changelog.properties
