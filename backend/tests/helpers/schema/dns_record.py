from typing import Any

from infrahub.core.schema import SchemaRoot

# One kind carrying both IPHost flavours side by side: attributes that declare `allow_prefix: false`
# and one that declares nothing at all. The undeclared `mgmt_ip` is the control -- it pins the
# pre-existing host/prefix behaviour so a regression on that path cannot hide behind a passing test
# for the declared path.
#
# Spelled as a plain dict rather than typed schema models on purpose: attribute parameters are
# validated from raw dicts, so this drives the same coercion path a user's YAML or JSON schema
# payload takes rather than bypassing it.
#
# `generate_template` is opted in so the profile and object-template kinds exist. Neither generated
# kind carries `dns_target` -- unique attributes are excluded from both -- so `v6_target` is the
# flagged attribute to assert against on a profile or a template.
DNS_RECORD_DEFINITION: dict[str, Any] = {
    "name": "DnsRecord",
    "namespace": "Testing",
    "label": "DNS Record",
    "display_label": "dns_target__value",
    "human_friendly_id": ["dns_target__value"],
    "generate_template": True,
    "attributes": [
        {"name": "dns_target", "kind": "IPHost", "unique": True, "parameters": {"allow_prefix": False}},
        {"name": "mgmt_ip", "kind": "IPHost", "optional": True},
        {"name": "v6_target", "kind": "IPHost", "optional": True, "parameters": {"allow_prefix": False}},
    ],
}

_DNS_RECORD_ROOT: dict[str, Any] = {"nodes": [DNS_RECORD_DEFINITION]}

DNS_RECORD_SCHEMA = SchemaRoot(**_DNS_RECORD_ROOT)
DNS_RECORD = DNS_RECORD_SCHEMA.nodes[0]
