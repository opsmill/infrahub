from __future__ import annotations

import ipaddress
import re
from inspect import isclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipStatus
from infrahub.core.models import NodeKind
from infrahub.core.query import QueryType
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from neo4j import Record
    from neo4j.graph import Node as Neo4jNode

    from infrahub.database import InfrahubDatabase


async def add_relationship(
    src_node_id: str,
    dst_node_id: str,
    rel_type: str,
    db: InfrahubDatabase,
    branch_name: str | None = None,
    branch_level: int | None = None,
    at: Timestamp | None = None,
    status: RelationshipStatus = RelationshipStatus.ACTIVE,
) -> Record | None:
    create_rel_query = """
    MATCH (s) WHERE %(id_func)s(s) = $src_node_id
    MATCH (d) WHERE %(id_func)s(d) = $dst_node_id
    WITH s,d
    CREATE (s)-[r:%(rel_type)s { branch: $branch, branch_level: $branch_level, from: $at, status: $status }]->(d)
    RETURN %(id_func)s(r)
    """ % {"id_func": db.get_id_function_name(), "rel_type": str(rel_type).upper()}

    at = Timestamp(at)

    params = {
        "src_node_id": db.to_database_id(src_node_id),
        "dst_node_id": db.to_database_id(dst_node_id),
        "at": at.to_string(),
        "branch": branch_name or registry.default_branch,
        "branch_level": branch_level or 1,
        "status": status.value,
    }

    results = await db.execute_query(query=create_rel_query, params=params, name="add_relationship")
    if not results:
        return None
    return results[0][0]


async def delete_all_relationships_for_branch(branch_name: str, db: InfrahubDatabase) -> None:
    query = """
    MATCH ()-[r { branch: $branch_name }]-() DELETE r
    """
    params = {"branch_name": branch_name}

    await db.execute_query(query=query, params=params, name="delete_all_relationships_for_branch")


async def update_relationships_to(
    ids: list[str], db: InfrahubDatabase, to: Timestamp | None = None
) -> list[Record] | None:
    """Update the "to" field on one or multiple relationships."""
    if not ids:
        return None

    to = Timestamp(to)

    query = """
    MATCH ()-[r]->()
    WHERE %(id_func)s(r) IN $ids
    AND r.to IS NULL
    SET r.to = $to
    RETURN %(id_func)s(r)
    """ % {"id_func": db.get_id_function_name()}

    params = {"to": to.to_string(), "ids": [db.to_database_id(_id) for _id in ids]}

    return await db.execute_query(query=query, params=params, name="update_relationships_to")


async def get_paths_between_nodes(
    db: InfrahubDatabase,
    source_id: str,
    destination_id: str,
    relationships: list[str] | None = None,
    max_length: int | None = None,
    print_query: bool = False,
) -> list[Record]:
    """Return all paths between 2 nodes."""

    length_limit = f"..{max_length}" if max_length else ""

    relationships_str = ""
    if isinstance(relationships, list):
        relationships_str = ":" + "|".join(relationships)

    query = """
    MATCH p = (s)-[%(rel)s*%(length_limit)s]-(d)
    WHERE %(id_func)s(s) = $source_id AND %(id_func)s(d) = $destination_id
    RETURN p
    """ % {"rel": relationships_str.upper(), "length_limit": length_limit, "id_func": db.get_id_function_name()}

    if print_query:
        print(query)

    params = {
        "source_id": db.to_database_id(source_id),
        "destination_id": db.to_database_id(destination_id),
    }

    return await db.execute_query(query=query, params=params, name="get_paths_between_nodes", type=QueryType.READ)


async def count_relationships(db: InfrahubDatabase, label: str | None = None) -> int:
    """Return the total number of relationships in the database."""

    label_str = f":{label}" if label else ""

    query = f"""
    MATCH ()-[r{label_str}]->()
    RETURN count(r) as count
    """

    params: dict = {}

    result = await db.execute_query(query=query, params=params, name="count_relationships", type=QueryType.READ)
    return result[0][0]


async def get_nodes(db: InfrahubDatabase, label: str) -> list[Neo4jNode]:
    """Return theall nodes of a given label in the database."""
    query = """
    MATCH (node:%(node_kind)s)
    RETURN node
    """ % {"node_kind": label}
    results = await db.execute_query(query=query, name="get_nodes", type=QueryType.READ)
    return [result[0] for result in results]


async def count_nodes(db: InfrahubDatabase, label: str | None = None) -> int:
    """Return the total number of nodes of a given label in the database."""

    label_str = f":{label}" if label else ""

    query = f"""
    MATCH (node{label_str})
    RETURN count(node) as count
    """
    params: dict = {"label": label}
    result = await db.execute_query(query=query, params=params, name="count_nodes", type=QueryType.READ)
    return result[0][0]


async def delete_all_nodes(db: InfrahubDatabase) -> list[Record]:
    query = """
    MATCH (n)
    DETACH DELETE n
    """

    params: dict = {}

    return await db.execute_query(query=query, params=params, name="delete_all_nodes")


def extract_field_filters(field_name: str, filters: dict) -> dict[str, Any]:
    """Extract the filters for a given field (attribute or relationship) from a filters dict."""
    return {
        key.replace(f"{field_name}__", ""): value for key, value in filters.items() if key.startswith(f"{field_name}__")
    }


def parse_node_kind(kind: str) -> NodeKind:
    KIND_REGEX = r"^([A-Z][a-z0-9]+)([A-Z][a-zA-Z0-9]+)$"

    if match := re.search(KIND_REGEX, kind):
        return NodeKind(namespace=match.group(1), name=match.group(2))

    raise ValueError("The String provided is not a valid Node kind")


def convert_ip_to_binary_str(
    obj: ipaddress.IPv6Network | ipaddress.IPv4Network | ipaddress.IPv4Interface | ipaddress.IPv6Interface,
) -> str:
    if isinstance(obj, ipaddress.IPv6Network | ipaddress.IPv4Network):
        prefix_bin = f"{int(obj.network_address):b}"
        return prefix_bin.zfill(obj.max_prefixlen)

    ip_bin = f"{int(obj):b}"
    return ip_bin.zfill(obj.max_prefixlen)


def build_regex_attrs(values: list[str | int | bool]) -> str:
    """Build a regex to match one or multiple values in a JSON string, mainly used to match on an attribute of type List"""
    return ".*(" + "|".join([build_regex_attr(value=value) for value in values]) + ").*"


def build_regex_attr(value: str | int | bool) -> str:
    """Build a single regex to match a value in a JSON string
    For a string, it must have quotes
    For int and bool, it must not have quotes
    """
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, bool | int):
        value_str = str(value).lower()
        return rf'(?<=[^\w"\d]){value_str}(?=[^\w"\d])'

    raise ValueError("value was neither a string, an int or a boolean")


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


def props(x: Any) -> dict[str, Any]:
    return {key: vars(x).get(key, getattr(x, key)) for key in dir(x) if key not in _all_vars}


class SubclassWithMeta_Meta(type):
    _meta = None

    def __str__(cls) -> str:
        if cls._meta:
            return cls._meta.name
        return cls.__name__

    def __repr__(cls) -> str:
        return f"<{cls.__name__} meta={repr(cls._meta)}>"


class SubclassWithMeta(metaclass=SubclassWithMeta_Meta):
    """This class improves __init_subclass__ to receive automatically the options from meta"""

    def __init_subclass__(cls, **meta_options: dict[str, Any]) -> None:
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
                f"Abstract types can only contain the abstract attribute. Received: abstract, {', '.join(options)}"
            )
        else:
            super_class = super(cls, cls)
            if hasattr(super_class, "__init_subclass_with_meta__"):
                super_class.__init_subclass_with_meta__(**options)

    @classmethod
    def __init_subclass_with_meta__(cls, **meta_options: dict[str, Any]) -> None:
        """This method just terminates the super() chain"""
