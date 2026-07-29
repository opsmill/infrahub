from typing import Any

from infrahub.core.schema import SchemaRoot

# Kinds that reach an `IPHost` attribute through something other than their own attribute list, so a
# lookup component has to be resolved against the peer schema rather than the schema being looked up.
#
# `TestingDnsZone` carries both flavours side by side, the same pairing the single-kind fixture uses:
# `zone_target` declares `allow_prefix: false` and `zone_mgmt_ip` declares nothing. Each is reached by
# its own delegation kind so the declared path and the undeclared control are asserted independently.
#
# The hierarchy repeats the pairing one level up, because a `parent` path is resolved through the
# hierarchy relationship rather than a relationship the schema author wrote.
#
# Spelled as plain dicts for the same reason the single-kind fixture is: attribute parameters are
# validated from raw dicts, so this drives the coercion path a user's schema payload takes.

DNS_ZONE_DEFINITION: dict[str, Any] = {
    "name": "DnsZone",
    "namespace": "Testing",
    "label": "DNS Zone",
    "display_label": "name__value",
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True},
        {"name": "zone_target", "kind": "IPHost", "unique": True, "parameters": {"allow_prefix": False}},
        {"name": "zone_mgmt_ip", "kind": "IPHost", "unique": True},
    ],
}

DECLARED_DELEGATION_DEFINITION: dict[str, Any] = {
    "name": "DeclaredDelegation",
    "namespace": "Testing",
    "label": "Declared Delegation",
    "human_friendly_id": ["zone__zone_target__value", "label__value"],
    "attributes": [{"name": "label", "kind": "Text"}],
    "relationships": [{"name": "zone", "peer": "TestingDnsZone", "cardinality": "one", "optional": False}],
}

UNDECLARED_DELEGATION_DEFINITION: dict[str, Any] = {
    "name": "UndeclaredDelegation",
    "namespace": "Testing",
    "label": "Undeclared Delegation",
    "human_friendly_id": ["zone__zone_mgmt_ip__value", "label__value"],
    "attributes": [{"name": "label", "kind": "Text"}],
    "relationships": [{"name": "zone", "peer": "TestingDnsZone", "cardinality": "one", "optional": False}],
}

ZONE_TREE_DEFINITION: dict[str, Any] = {
    "name": "ZoneTree",
    "namespace": "Testing",
    "label": "Zone Tree",
    "display_label": "name__value",
    "hierarchical": True,
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True},
        {"name": "tree_target", "kind": "IPHost", "unique": True, "parameters": {"allow_prefix": False}},
        {"name": "tree_mgmt_ip", "kind": "IPHost", "unique": True, "optional": True},
    ],
}

ZONE_ROOT_DEFINITION: dict[str, Any] = {
    "name": "ZoneRoot",
    "namespace": "Testing",
    "label": "Zone Root",
    "inherit_from": ["TestingZoneTree"],
    "parent": "",
    "children": "",
}

ZONE_LEAF_DEFINITION: dict[str, Any] = {
    "name": "ZoneLeaf",
    "namespace": "Testing",
    "label": "Zone Leaf",
    "inherit_from": ["TestingZoneTree"],
    "parent": "TestingZoneRoot",
    "children": "",
    "human_friendly_id": ["parent__tree_target__value", "name__value"],
}

ZONE_MGMT_LEAF_DEFINITION: dict[str, Any] = {
    "name": "ZoneMgmtLeaf",
    "namespace": "Testing",
    "label": "Zone Mgmt Leaf",
    "inherit_from": ["TestingZoneTree"],
    "parent": "TestingZoneRoot",
    "children": "",
    "human_friendly_id": ["parent__tree_mgmt_ip__value", "name__value"],
}

_DNS_DELEGATION_ROOT: dict[str, Any] = {
    "generics": [ZONE_TREE_DEFINITION],
    "nodes": [
        DNS_ZONE_DEFINITION,
        DECLARED_DELEGATION_DEFINITION,
        UNDECLARED_DELEGATION_DEFINITION,
        ZONE_ROOT_DEFINITION,
        ZONE_LEAF_DEFINITION,
        ZONE_MGMT_LEAF_DEFINITION,
    ],
}

DNS_DELEGATION_SCHEMA = SchemaRoot(**_DNS_DELEGATION_ROOT)
