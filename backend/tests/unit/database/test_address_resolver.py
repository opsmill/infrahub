from neo4j import Address

from infrahub.database import build_address_resolver


def test_resolver_expands_initial_address() -> None:
    resolver = build_address_resolver(members=["member1", "member2:7777", "member3"], default_port=7687)

    resolved = resolver(Address(("member1", 7687)))

    assert resolved == [
        Address(("member1", 7687)),
        Address(("member2", 7777)),
        Address(("member3", 7687)),
    ]


def test_resolver_passes_through_other_addresses() -> None:
    resolver = build_address_resolver(members=["member1", "member2"], default_port=7687)

    routing_address = Address(("member2", 7687))
    assert resolver(routing_address) == [routing_address]

    other_address = Address(("unknown-server", 7687))
    assert resolver(other_address) == [other_address]
