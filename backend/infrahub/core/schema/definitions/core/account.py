from infrahub.core.constants import (
    AccountStatus,
    AccountType,
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality

from ...attribute_schema import AttributeSchema as Attr
from ...dropdown import DropdownChoice
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_account = NodeSchema(
    name="Account",
    namespace="Core",
    description="User Account for Infrahub",
    include_in_menu=False,
    label="Account",
    icon="mdi:account",
    default_filter="name__value",
    order_by=["name__value"],
    display_label="label__value",
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.LINEAGEOWNER, InfrahubKind.LINEAGESOURCE, InfrahubKind.GENERICACCOUNT],
)

core_account_token = NodeSchema(
    name="AccountToken",
    namespace="Internal",
    description="Token for User Account",
    include_in_menu=False,
    label="Account Token",
    default_filter="token__value",
    display_label="token__value",
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["token__value"]],
    documentation="/topics/auth",
    attributes=[
        Attr(name="name", kind="Text", optional=True),
        Attr(name="token", kind="Text", description="The authentication token value", unique=True),
        Attr(name="expiration", kind="DateTime", description="Date and time when the token expires", optional=True),
    ],
    relationships=[
        Rel(
            name="account",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=False,
            cardinality=Cardinality.ONE,
            identifier="account__token",
        ),
    ],
)

core_password_credential = NodeSchema(
    name="PasswordCredential",
    namespace="Core",
    description="Username/Password based credential",
    include_in_menu=False,
    label="Username / Password",
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.CREDENTIAL],
    attributes=[
        Attr(name="username", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC, order_weight=6000),
        Attr(name="password", kind="Password", optional=True, branch=BranchSupportType.AGNOSTIC, order_weight=7000),
    ],
)

core_refresh_token = NodeSchema(
    name="RefreshToken",
    namespace="Internal",
    description="Refresh Token",
    include_in_menu=False,
    label="Refresh Token",
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(
            name="expiration",
            kind="DateTime",
            description="Date and time when the refresh token expires",
            optional=False,
        ),
    ],
    relationships=[
        Rel(
            name="account",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=False,
            cardinality=Cardinality.ONE,
            identifier="account__refreshtoken",
        ),
    ],
)

core_credential = GenericSchema(
    name="Credential",
    namespace="Core",
    description="A credential that could be referenced to access external services.",
    include_in_menu=False,
    label="Credential",
    default_filter="name__value",
    order_by=["name__value"],
    display_label="label__value",
    icon="mdi:key-variant",
    human_friendly_id=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    documentation="/topics/auth",
    restricted_namespaces=["Core"],
    attributes=[
        Attr(name="name", kind="Text", unique=True, order_weight=1000),
        Attr(name="label", kind="Text", optional=True, order_weight=2000),
        Attr(name="description", kind="Text", optional=True, order_weight=3000),
    ],
)

core_generic_account = GenericSchema(
    name="GenericAccount",
    namespace="Core",
    description="User Account for Infrahub",
    include_in_menu=False,
    label="Account",
    icon="mdi:account",
    default_filter="name__value",
    order_by=["name__value"],
    display_label="label__value",
    human_friendly_id=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    documentation="/topics/auth",
    uniqueness_constraints=[["name__value"]],
    restricted_namespaces=["Core"],
    attributes=[
        Attr(name="name", kind="Text", unique=True),
        Attr(name="password", kind="HashedPassword", unique=False),
        Attr(name="label", kind="Text", optional=True),
        Attr(name="description", kind="Text", optional=True),
        Attr(
            name="account_type",
            kind="Text",
            description="Type of account (user, script, etc.)",
            default_value=AccountType.USER.value,
            enum=AccountType.available_types(),
        ),
        Attr(
            name="status",
            kind="Dropdown",
            choices=[
                DropdownChoice(
                    name=AccountStatus.ACTIVE.value,
                    label="Active",
                    description="Account is allowed to login",
                    color="#52be80",
                ),
                DropdownChoice(
                    name=AccountStatus.INACTIVE.value,
                    label="Inactive",
                    description="Account is not allowed to login",
                    color="#e74c3c",
                ),
            ],
            default_value=AccountStatus.ACTIVE.value,
        ),
    ],
    relationships=[
        Rel(
            name="tokens",
            peer=InfrahubKind.ACCOUNTTOKEN,
            optional=True,
            cardinality=Cardinality.MANY,
            identifier="account__token",
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
        Rel(
            name="external_identities",
            peer=InfrahubKind.EXTERNALIDENTITY,
            optional=True,
            cardinality=Cardinality.MANY,
            identifier="account__external_identity",
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
    ],
)

internal_external_identity = NodeSchema(
    name="ExternalIdentity",
    namespace="Internal",
    description="External authentication provider identity linked to an account",
    include_in_menu=False,
    label="External Identity",
    display_label="{{ protocol__value }}:{{ provider_name__value }}:{{ sub__value }}",
    human_friendly_id=["protocol__value", "provider_name__value", "sub__value"],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["sub__value", "provider_name__value", "protocol__value"]],
    attributes=[
        Attr(name="sub", kind="Text", description="The provider-issued subject identifier"),
        Attr(
            name="provider_name",
            kind="Text",
            description="The provider name as configured in Infrahub, e.g. 'google', 'provider1'",
        ),
        Attr(
            name="protocol", kind="Text", description="The authentication protocol used, e.g. 'oidc', 'oauth2', 'ldap'"
        ),
    ],
    relationships=[
        Rel(
            name="account",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=False,
            cardinality=Cardinality.ONE,
            identifier="account__external_identity",
        ),
    ],
)
