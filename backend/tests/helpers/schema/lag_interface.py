from typing import Any

from infrahub.core.constants import RelationshipCardinality, RelationshipKind

LAG_INTERFACE: dict[str, Any] = {
    "name": "LagInterface",
    "namespace": "Infra",
    "label": "LAG Interface",
    "include_in_menu": False,
    "default_filter": "name__value",
    "display_labels": ["name__value"],
    "containers": [
        {"name": "lacp", "label": "LACP", "order_weight": 100},
        {
            "name": "layer2",
            "label": "Layer 2",
            "description": "Switching settings of the bundle",
            "order_weight": 200,
        },
        {"name": "layer3", "label": "Layer 3", "order_weight": 300, "collapsed": True},
    ],
    "attributes": [
        {"name": "name", "kind": "Text", "order_weight": 1000},
        {"name": "description", "kind": "Text", "optional": True, "order_weight": 2000},
        {"name": "lacp_rate", "kind": "Text", "optional": True, "container": "lacp", "order_weight": 3000},
        {"name": "lacp_mode", "kind": "Text", "optional": True, "container": "lacp", "order_weight": 4000},
        {"name": "l2_mode", "kind": "Text", "optional": True, "container": "layer2", "order_weight": 5000},
        {
            "name": "mac_address",
            "kind": "MacAddress",
            "optional": True,
            "container": "layer2",
            "display": "extra",
            "order_weight": 6000,
        },
        {"name": "mtu", "kind": "Number", "optional": True, "container": "layer3", "order_weight": 7000},
    ],
    "relationships": [
        {
            "name": "sub_interfaces",
            "peer": "InfraLagInterface",
            "kind": RelationshipKind.GENERIC.value,
            "cardinality": RelationshipCardinality.MANY.value,
            "optional": True,
            "container": "layer2",
            "order_weight": 8000,
        },
    ],
}

LAG_INTERFACE_L2: dict[str, Any] = {
    "name": "LagInterfaceL2",
    "namespace": "Infra",
    "label": "LAG Interface L2",
    "include_in_menu": True,
    "inherit_from": ["InfraLagInterface"],
}

LAG_INTERFACE_L3: dict[str, Any] = {
    "name": "LagInterfaceL3",
    "namespace": "Infra",
    "label": "LAG Interface L3",
    "include_in_menu": True,
    "inherit_from": ["InfraLagInterface"],
    "containers": [
        {"name": "layer3", "label": "Layer 3 (routed)", "order_weight": 300, "collapsed": True},
    ],
}

LAG_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "generics": [LAG_INTERFACE],
    "nodes": [LAG_INTERFACE_L2, LAG_INTERFACE_L3],
}
