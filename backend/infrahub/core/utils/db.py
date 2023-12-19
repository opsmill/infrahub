from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import infrahub.config as config
from infrahub.core.constants import RelationshipStatus
from infrahub.core.timestamp import Timestamp

from .query import element_id_to_id

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


async def add_relationship(
    src_node_id: str,
    dst_node_id: str,
    rel_type: str,
    db: InfrahubDatabase,
    branch_name: Optional[str] = None,
    branch_level: Optional[int] = None,
    at: Optional[Timestamp] = None,
    status=RelationshipStatus.ACTIVE,
):
    create_rel_query = """
    MATCH (s) WHERE ID(s) = $src_node_id
    MATCH (d) WHERE ID(d) = $dst_node_id
    WITH s,d
    CREATE (s)-[r:%s { branch: $branch, branch_level: $branch_level, from: $at, to: null, status: $status }]->(d)
    RETURN ID(r)
    """ % str(rel_type).upper()

    at = Timestamp(at)

    params = {
        "src_node_id": element_id_to_id(src_node_id),
        "dst_node_id": element_id_to_id(dst_node_id),
        "at": at.to_string(),
        "branch": branch_name or config.SETTINGS.main.default_branch,
        "branch_level": branch_level or 1,
        "status": status.value,
    }

    results = await db.execute_query(
        query=create_rel_query,
        params=params,
    )
    if not results:
        return None
    return results[0][0]


async def update_relationships_to(
    ids: List[str],
    db: InfrahubDatabase,
    to: Timestamp = None,
):
    """Update the "to" field on one or multiple relationships."""
    if not ids:
        return None

    list_matches = [f"id(r) = {element_id_to_id(id)}" for id in ids]

    to = Timestamp(to)

    query = f"""
    MATCH ()-[r]->()
    WHERE {' or '.join(list_matches)}
    SET r.to = $to
    RETURN ID(r)
    """

    params = {"to": to.to_string()}

    return await db.execute_query(query=query, params=params)


async def get_paths_between_nodes(
    db: InfrahubDatabase,
    source_id: str,
    destination_id: str,
    relationships: Optional[List[str]] = None,
    max_length: Optional[int] = None,
    print_query=False,
):
    """Return all paths between 2 nodes."""

    length_limit = f"..{max_length}" if max_length else ""

    relationships_str = ""
    if isinstance(relationships, list):
        relationships_str = ":" + "|".join(relationships)

    query = """
    MATCH p = (s)-[%s*%s]-(d)
    WHERE ID(s) = $source_id AND ID(d) = $destination_id
    RETURN p
    """ % (
        relationships_str.upper(),
        length_limit,
    )

    if print_query:
        print(query)

    params = {
        "source_id": element_id_to_id(source_id),
        "destination_id": element_id_to_id(destination_id),
    }

    return await db.execute_query(query=query, params=params, name="get_paths_between_nodes")


async def count_relationships(db: InfrahubDatabase) -> int:
    """Return the total number of relationships in the database."""
    query = """
    MATCH ()-[r]->()
    RETURN count(r) as count
    """

    params: dict = {}

    result = await db.execute_query(query=query, params=params)
    return result[0][0]


async def delete_all_nodes(db: InfrahubDatabase):
    query = """
    MATCH (n)
    DETACH DELETE n
    """

    params: dict = {}

    return await db.execute_query(query=query, params=params)
