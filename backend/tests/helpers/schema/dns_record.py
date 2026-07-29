from typing import Any

from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import IPHostAttributeParameters

# One kind carrying both IPHost flavours side by side: attributes that declare `allow_prefix: false`
# and one that declares nothing at all. `generate_template` is opted in so the profile and
# object-template kinds exist.
DNS_RECORD = NodeSchema(
    name="DnsRecord",
    namespace="Testing",
    label="DNS Record",
    display_label="dns_target__value",
    human_friendly_id=["dns_target__value"],
    generate_template=True,
    attributes=[
        AttributeSchema(
            name="dns_target",
            kind="IPHost",
            unique=True,
            parameters=IPHostAttributeParameters(allow_prefix=False),
        ),
        AttributeSchema(name="mgmt_ip", kind="IPHost", optional=True),
        AttributeSchema(
            name="v6_target",
            kind="IPHost",
            optional=True,
            parameters=IPHostAttributeParameters(allow_prefix=False),
        ),
    ],
)

DNS_RECORD_SCHEMA = SchemaRoot(nodes=[DNS_RECORD])

DNS_RECORD_DICT: dict[str, Any] = DNS_RECORD.to_dict()
