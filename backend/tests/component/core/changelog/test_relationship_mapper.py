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
    """Adding a one-cardinality peer records the edge's source, owner and is_protected metadata."""
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    owner = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    edge_source = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await edge_source.new(db=db, name="Source")
    await edge_source.save(db=db)
    edge_owner = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await edge_owner.new(db=db, name="Owner")
    await edge_owner.save(db=db)
    dog = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=owner)
    await dog.save(db=db)

    owner_rel_schema = dog_schema.get_relationship(name="owner")
    relationship = Relationship(schema=owner_rel_schema, branch=default_branch, node=dog, source_kind=dog.get_kind())
    await relationship.new(
        db=db,
        data={
            "id": owner.id,
            "_relation__source": edge_source.id,
            "_relation__owner": edge_owner.id,
            "_relation__is_protected": True,
        },
    )

    mapper = ChangelogRelationshipMapper(schema=owner_rel_schema)
    mapper.add_peer_from_relationship(relationship=relationship)

    changelog = mapper.changelog
    assert isinstance(changelog, RelationshipCardinalityOneChangelog)
    assert changelog.peer_id == owner.id
    assert changelog.properties["source"].value == edge_source.id
    assert changelog.properties["owner"].value == edge_owner.id
    assert changelog.properties["is_protected"].value is True
