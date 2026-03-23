"""Tests for neo4j notification suppression for optional relationship types.

When a Neo4j database (especially clustered) does not contain any HAS_OWNER or HAS_SOURCE
relationships, queries that reference these types via explicit pattern matching
(e.g., `OPTIONAL MATCH (a)-[r:HAS_OWNER]-(b)`) trigger noisy warnings:

    "warn: relationship type does not exist. The relationship type `HAS_OWNER`
     does not exist in database..."

The fix is to avoid explicit relationship type patterns in OPTIONAL MATCH clauses
for optional metadata relationship types. Instead, queries should use generic patterns
with type() checks in WHERE clauses.

See: https://github.com/opsmill/infrahub/issues/8620
"""

import re

from infrahub.core.branch import Branch
from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.query.relationship import (
    RelationshipDeleteQuery,
    RelationshipGetPeerQuery,
)
from infrahub.core.relationship import Relationship
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

# Regex to find explicit HAS_OWNER or HAS_SOURCE in OPTIONAL MATCH relationship type patterns.
# This matches patterns like:
#   OPTIONAL MATCH (x)-[r:HAS_OWNER]-(y)
#   OPTIONAL MATCH (x)-[edge:IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(y)
# But NOT patterns like:
#   WHERE type(r) = "HAS_OWNER"
#   type(r_prop) IN ["IS_PROTECTED", "HAS_SOURCE", "HAS_OWNER", ...]
EXPLICIT_REL_TYPE_IN_MATCH_PATTERN = re.compile(
    r"OPTIONAL\s+MATCH\s+.*\[.*:.*(?:HAS_OWNER|HAS_SOURCE).*\]",
    re.IGNORECASE | re.DOTALL,
)


async def test_relationship_get_peer_query_no_explicit_owner_source_in_optional_match(
    db: InfrahubDatabase,
    person_jack_tags_main: Node,
    branch: Branch,
) -> None:
    """RelationshipGetPeerQuery should not use explicit HAS_OWNER/HAS_SOURCE types in OPTIONAL MATCH.

    When metadata for owner and source is requested, the generated Cypher query should
    avoid explicit relationship type patterns like `[r:HAS_OWNER]` in OPTIONAL MATCH
    clauses, because these trigger warnings in Neo4j (especially clustered) when the
    relationship type does not exist in the database.

    Instead, queries should use generic patterns with type() filters in WHERE clauses.
    """
    from infrahub.core import registry

    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_jack_tags_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
        include_metadata=MetadataOptions.OWNER | MetadataOptions.SOURCE,
    )

    generated_cypher = query.get_query()

    # The generated query must NOT contain explicit HAS_OWNER or HAS_SOURCE
    # relationship types in OPTIONAL MATCH patterns
    matches = EXPLICIT_REL_TYPE_IN_MATCH_PATTERN.findall(generated_cypher)
    assert not matches, (
        f"Generated Cypher contains explicit HAS_OWNER/HAS_SOURCE in OPTIONAL MATCH patterns, "
        f"which triggers neo4j warnings when these relationship types don't exist in the database. "
        f"Problematic patterns found: {matches}"
    )


async def test_node_list_get_attribute_query_no_explicit_owner_source_in_optional_match(
    db: InfrahubDatabase,
    person_jack_tags_main: Node,
    default_branch: Branch,
) -> None:
    """NodeListGetAttributeQuery should not use explicit HAS_OWNER/HAS_SOURCE types in OPTIONAL MATCH.

    This covers both _add_source_to_query() and _add_owner_to_query() which generate
    OPTIONAL MATCH clauses with explicit relationship types.
    """
    query = await NodeListGetAttributeQuery.init(
        db=db,
        ids=[person_jack_tags_main.id],
        branch=default_branch,
        include_metadata=MetadataOptions.OWNER | MetadataOptions.SOURCE,
    )

    generated_cypher = query.get_query()

    matches = EXPLICIT_REL_TYPE_IN_MATCH_PATTERN.findall(generated_cypher)
    assert not matches, (
        f"Generated Cypher contains explicit HAS_OWNER/HAS_SOURCE in OPTIONAL MATCH patterns, "
        f"which triggers neo4j warnings when these relationship types don't exist in the database. "
        f"Problematic patterns found: {matches}"
    )


async def test_relationship_delete_query_no_explicit_owner_source_in_optional_match(
    db: InfrahubDatabase,
    person_jack_tags_main: Node,
    tag_blue_main: Node,
    default_branch: Branch,
) -> None:
    """RelationshipDeleteQuery should not use explicit HAS_OWNER/HAS_SOURCE types in OPTIONAL MATCH.

    The delete query uses `OPTIONAL MATCH (rl)-[edge:IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(peer)`
    which triggers neo4j warnings when those relationship types don't exist.
    """
    from infrahub.core import registry

    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    jack_main = await NodeManager.get_one(db=db, id=person_jack_tags_main.id)
    tags_rels = await jack_main.tags.get(db=db)
    blue_tag_rel = [t for t in tags_rels if t.peer_id == tag_blue_main.id][0]

    query = await RelationshipDeleteQuery.init(
        db=db,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=blue_tag_rel,
        branch=default_branch,
        source_branch=default_branch,
        destination_branch=default_branch,
        at=Timestamp(),
    )

    generated_cypher = query.get_query()

    matches = EXPLICIT_REL_TYPE_IN_MATCH_PATTERN.findall(generated_cypher)
    assert not matches, (
        f"Generated Cypher contains explicit HAS_OWNER/HAS_SOURCE in OPTIONAL MATCH patterns, "
        f"which triggers neo4j warnings when these relationship types don't exist in the database. "
        f"Problematic patterns found: {matches}"
    )
