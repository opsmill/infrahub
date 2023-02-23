from __future__ import annotations

from inspect import isclass
from typing import TYPE_CHECKING, List, Optional

import infrahub.config as config
from infrahub.core.constants import RelationshipStatus
from infrahub.core.timestamp import Timestamp
from infrahub.database import execute_read_query_async, execute_write_query_async

if TYPE_CHECKING:
    from neo4j import AsyncSession


async def add_relationship(
    src_node_id: str,
    dst_node_id: str,
    rel_type: str,
    session: AsyncSession,
    branch_name: Optional[str] = None,
    at: Optional[Timestamp] = None,
    status=RelationshipStatus.ACTIVE,
):
    create_rel_query = (
        """
    MATCH (s) WHERE ID(s) = $src_node_id
    MATCH (d) WHERE ID(d) = $dst_node_id
    WITH s,d
    CREATE (s)-[r:%s { branch: $branch, from: $at, to: null, status: $status }]->(d)
    RETURN ID(r)
    """
        % str(rel_type).upper()
    )

    at = Timestamp(at)

    params = {
        "src_node_id": element_id_to_id(src_node_id),
        "dst_node_id": element_id_to_id(dst_node_id),
        "at": at.to_string(),
        "branch": branch_name or config.SETTINGS.main.default_branch,
        "status": status.value,
    }

    results = await execute_write_query_async(
        session=session,
        query=create_rel_query,
        params=params,
    )
    if not results:
        return None
    return results[0][0]


async def delete_all_relationships_for_branch(branch_name: str, session: AsyncSession):
    query = """
    MATCH ()-[r { branch: $branch_name }]-() DELETE r
    """
    params = {"branch_name": branch_name}

    await execute_write_query_async(session=session, query=query, params=params)


async def update_relationships_to(
    ids: List[str],
    session: AsyncSession,
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

    return await execute_write_query_async(session=session, query=query, params=params)


async def get_paths_between_nodes(
    session: AsyncSession,
    source_id: str,
    destination_id: str,
    relationships: List[str] = None,
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

    return await execute_read_query_async(session=session, query=query, params=params)


async def delete_all_nodes(session: AsyncSession):
    query = """
    MATCH (n)
    DETACH DELETE n
    """

    params = {}

    return await execute_write_query_async(session=session, query=query, params=params)


def element_id_to_id(element_id: str) -> int:
    return int(element_id.split(":")[2])


# --------------------------------------------------------------------------------
# CODE IMPORTED FROM:
#   https://github.com/graphql-python/graphene/blob/9c3e4bb7da001aac48002a3b7d83dcd072087770/graphene/utils/subclass_with_meta.py#L18
#   https://github.com/graphql-python/graphene/blob/9c3e4bb7da001aac48002a3b7d83dcd072087770/graphene/utils/props.py#L12
# --------------------------------------------------------------------------------


class _OldClass:
    pass


class _NewClass:
    pass


_all_vars = set(dir(_OldClass) + dir(_NewClass))


def props(x):
    return {key: vars(x).get(key, getattr(x, key)) for key in dir(x) if key not in _all_vars}


class SubclassWithMeta_Meta(type):
    _meta = None

    def __str__(cls):
        if cls._meta:
            return cls._meta.name
        return cls.__name__

    def __repr__(cls):
        return f"<{cls.__name__} meta={repr(cls._meta)}>"


class SubclassWithMeta(metaclass=SubclassWithMeta_Meta):
    """This class improves __init_subclass__ to receive automatically the options from meta"""

    def __init_subclass__(cls, **meta_options):
        """This method just terminates the super() chain"""
        _Meta = getattr(cls, "Meta", None)
        _meta_props = {}
        if _Meta:
            if isinstance(_Meta, dict):
                _meta_props = _Meta
            elif isclass(_Meta):
                _meta_props = props(_Meta)
            else:
                raise TypeError(f"Meta have to be either a class or a dict. Received {_Meta}")
            delattr(cls, "Meta")
        options = dict(meta_options, **_meta_props)

        abstract = options.pop("abstract", False)
        if abstract:
            assert not options, (
                "Abstract types can only contain the abstract attribute. " f"Received: abstract, {', '.join(options)}"
            )
        else:
            super_class = super(cls, cls)
            if hasattr(super_class, "__init_subclass_with_meta__"):
                super_class.__init_subclass_with_meta__(**options)

    @classmethod
    def __init_subclass_with_meta__(cls, **meta_options):
        """This method just terminates the super() chain"""
