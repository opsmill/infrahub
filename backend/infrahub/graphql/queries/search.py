from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node, is_valid_uuid

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.protocols import CoreNode
    from infrahub.graphql.initialization import GraphqlContext


class Node(ObjectType):
    id = Field(String, required=True)
    kind = Field(String, required=True, description="The node kind")


class NodeEdge(ObjectType):
    node = Field(Node, required=True)


class NodeEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=NonNull(NodeEdge)), required=True)


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


async def search_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    q: str,
    limit: int = 10,
    partial_match: bool = True,
) -> dict[str, Any]:
    graphql_context: GraphqlContext = info.context
    response: dict[str, Any] = {}
    results: list[CoreNode] = []

    fields = await extract_fields_first_node(info)

    if is_valid_uuid(q):
        matching: CoreNode | None = await NodeManager.get_one(
            db=graphql_context.db, branch=graphql_context.branch, at=graphql_context.at, id=q
        )
        if matching:
            results.append(matching)
    else:
        try:
            # Convert any IPv6 address, network or partial address to collapsed format as it might be stored in db.
            q = _collapse_ipv6(q)
        except (ValueError, ipaddress.AddressValueError):
            pass

        for kind in [InfrahubKind.NODE, InfrahubKind.GENERICGROUP]:
            objs = await NodeManager.query(
                db=graphql_context.db,
                branch=graphql_context.branch,
                schema=kind,
                filters={"any__value": q},
                limit=limit,
                partial_match=partial_match,
            )
            results.extend(objs)

    if "edges" in fields:
        response["edges"] = [{"node": {"id": obj.id, "kind": obj.get_kind()}} for obj in results]

    if "count" in fields:
        response["count"] = len(results)

    return response


InfrahubSearchAnywhere = Field(
    NodeEdges,
    q=String(required=True),
    limit=Int(required=False),
    partial_match=Boolean(required=False),
    resolver=search_resolver,
    required=True,
)
