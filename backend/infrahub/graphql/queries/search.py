from __future__ import annotations

import contextlib
import ipaddress
from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import is_valid_uuid

from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.query.ipam import IPParentPrefixLookupQuery
from infrahub.core.query.node import NodeGetListByAttributeValueQuery
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.utils import extract_camelcase_words

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class Node(ObjectType):
    id = Field(String, required=True)
    kind = Field(String, required=True, description="The node kind")


class NodeEdge(ObjectType):
    node = Field(Node, required=True)


class NodeEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=NonNull(NodeEdge)), required=True)
    parent_prefixes = Field(List(of_type=NonNull(NodeEdge)), required=False)


def _collapse_ipv6(s: str) -> str:
    """Collapse an ipv6 address, ipv6 network, or a partial ipv6 address in extended format, into its collapsed form.
    Raises an error if input does not resemble an IPv6 address in extended format. It means this function also raises
    an error if input string is the start of an IPv6 address in collapsed format.
    """

    try:
        return str(ipaddress.IPv6Address(s))
    except ipaddress.AddressValueError:
        pass

    try:
        return ipaddress.IPv6Network(s).with_prefixlen
    except ipaddress.AddressValueError:
        pass

    # Input string might be an incomplete address in IPv6 format,
    # in which case we would like the collapsed form equivalent of this incomplete address for matching purposes.
    # To get it, we first try to pad the incomplete address with zeros, then we retrieve the collapsed form
    # of the full address, and we remove extra "::" or ":0" at the end of it.

    error_message = "Input string does not match IPv6 extended format"

    # Input string cannot be an IPv6 in extended format if it contains ":"
    if "::" in s:
        raise ValueError(error_message)

    # Add padding to complete the address if needed
    segments = s.split(":")

    if len(segments) == 0:
        raise ValueError(error_message)

    # If any of the non-last segments has less than 4 characters it means we deal with
    # a IPv6 collapsed form or an invalid address
    for segment in segments[:-1]:
        if len(segment) != 4:
            raise ValueError(error_message)

    # Add 0 padding to last segment
    if len(segments[-1]) > 4:
        raise ValueError(error_message)

    segments[-1] += "0" * (4 - len(segments[-1]))

    # Complete the address to have 8 segments by padding with zeros
    while len(segments) < 8:
        segments.append("0000")

    # Create a full IPv6 address from the partial input
    full_address = ":".join(segments)

    # Create an IPv6Address object for validation and to build IPv6 collapsed form.
    ipv6_address = ipaddress.IPv6Address(full_address)

    compressed_address = ipv6_address.compressed

    # We padded with zeros so address might endswith "::" or ":0".
    if compressed_address.endswith(("::", ":0")):
        return compressed_address[:-2]

    # Otherwise, it means 8th segment of ipv6 address was not full and not composed of 0 only
    # e.g. 2001:0db8:0000:0000:0000:0000:03
    return compressed_address


def _try_parse_ip_or_prefix(
    q: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    """Try to parse a query string as an IP address or CIDR prefix.

    Returns the parsed object or None if the string is not a valid IP/CIDR.
    """
    with contextlib.suppress(ValueError):
        return ipaddress.ip_address(q)
    with contextlib.suppress(ValueError):
        return ipaddress.ip_network(q, strict=False)
    return None


def compute_allowed_search_kinds(graphql_context: GraphqlContext) -> list[str] | None:
    """Compute the list of node kinds the current user is allowed to view via search.

    Returns None if the user is a super admin (no filtering needed — zero overhead).
    Returns a list of allowed kind strings for restricted users.
    """
    if not graphql_context.permissions or graphql_context.permissions.is_super_admin():
        return None

    permission_manager = graphql_context.permissions

    # Determine required decision level based on branch context
    branch_name = graphql_context.branch.name if graphql_context.branch else None
    required_decision = (
        PermissionDecisionFlag.ALLOW_DEFAULT
        if branch_name is None or branch_name in (GLOBAL_BRANCH_NAME, registry.default_branch)
        else PermissionDecisionFlag.ALLOW_OTHER
    )

    full_schema = registry.get_full_schema(branch=graphql_context.branch, duplicate=False)

    allowed_kinds: list[str] = []
    for kind in full_schema:
        extracted_words = extract_camelcase_words(kind)
        permission = ObjectPermission(
            namespace=extracted_words[0],
            name="".join(extracted_words[1:]),
            action="view",
            decision=required_decision,
        )
        if permission_manager.resolve_object_permission(permission):
            allowed_kinds.append(kind)

    return allowed_kinds


async def search_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    q: str,
    limit: int = 10,
    offset: int = 0,
    partial_match: bool = True,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    if limit < 0:
        limit = 10
    offset = max(offset, 0)

    graphql_context: GraphqlContext = info.context
    response: dict[str, Any] = {}
    results: list[dict[str, str]] = []

    fields = extract_graphql_fields(info=info)

    # Compute permission-based kind filter
    allowed_kinds = compute_allowed_search_kinds(graphql_context)
    if allowed_kinds is not None and len(allowed_kinds) == 0:
        # User has no read permissions for any type — short-circuit
        if "count" in fields:
            response["count"] = 0
        if "edges" in fields:
            response["edges"] = []
        return response

    if is_valid_uuid(q):
        matching = await NodeManager.get_one(
            db=graphql_context.db, branch=graphql_context.branch, at=graphql_context.at, id=q
        )
        if matching:
            # For UUID lookups, check permission for the matched kind
            if allowed_kinds is None or matching.get_kind() in allowed_kinds:
                results.append({"id": matching.id, "kind": matching.get_kind()})
    else:
        with contextlib.suppress(ValueError, ipaddress.AddressValueError):
            # Convert any IPv6 address, network or partial address to collapsed format as it might be stored in db.
            q = _collapse_ipv6(q)

        # Detect if the query is a valid IP address or CIDR prefix for parent prefix lookup
        parsed_ip = _try_parse_ip_or_prefix(q)
        if parsed_ip is not None and "parent_prefixes" in fields:
            prefix_query = await IPParentPrefixLookupQuery.init(
                db=graphql_context.db, branch=graphql_context.branch, at=graphql_context.at, ip_value=parsed_ip
            )
            await prefix_query.execute(db=graphql_context.db)
            parent_prefix_results = [
                {"node": {"id": result.prefix_id, "kind": result.prefix_kind}} for result in prefix_query.get_data()
            ]
            response["parent_prefixes"] = parent_prefix_results

        query = await NodeGetListByAttributeValueQuery.init(
            db=graphql_context.db,
            branch=graphql_context.branch,
            at=graphql_context.at,
            search_value=q,
            kinds=[InfrahubKind.NODE, InfrahubKind.GENERICGROUP],
            limit=limit,
            offset=offset,
            partial_match=partial_match,
            case_insensitive=not case_sensitive,
            allowed_kinds=allowed_kinds,
        )
        await query.execute(db=graphql_context.db)

        for result in query.get_data():
            results.append({"id": result.uuid, "kind": result.kind})

    if "count" in fields:
        if is_valid_uuid(q):
            response["count"] = len(results)
        else:
            response["count"] = await query.count(db=graphql_context.db)

    if "edges" in fields:
        response["edges"] = [{"node": result} for result in results]

    return response


InfrahubSearchAnywhere = Field(
    NodeEdges,
    q=String(required=True),
    limit=Int(required=False),
    offset=Int(required=False),
    partial_match=Boolean(required=False),
    case_sensitive=Boolean(required=False),
    resolver=search_resolver,
    required=True,
)
