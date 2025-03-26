from infrahub.core.constants import (
    AccountStatus,
    AccountType,
    BranchSupportType,
    InfrahubKind,
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
    display_labels=["label__value"],
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
    display_labels=["token__value"],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["token__value"]],
    documentation="/topics/auth",
    attributes=[
        Attr(name="name", kind="Text", optional=True),
        Attr(name="token", kind="Text", unique=True),
        Attr(name="expiration", kind="DateTime", optional=True),
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
        Attr(
            name="password",
            kind="Password",
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
            order_weight=7000,
        ),
    ],
)

core_refresh_token = NodeSchema(
    name="RefreshToken",
    namespace="Internal",
    description="Refresh Token",
    include_in_menu=False,
    label="Refresh Token",
    display_labels=[],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="expiration", kind="DateTime", optional=False),
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
    display_labels=["label__value"],
    icon="mdi:key-variant",
    human_friendly_id=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    documentation="/topics/auth",
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
    display_labels=["label__value"],
    human_friendly_id=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    documentation="/topics/auth",
    uniqueness_constraints=[["name__value"]],
    attributes=[
        Attr(name="name", kind="Text", unique=True),
        Attr(name="password", kind="HashedPassword", unique=False),
        Attr(name="label", kind="Text", optional=True),
        Attr(name="description", kind="Text", optional=True),
        Attr(
            name="account_type",
            kind="Text",
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
    relationships=[Rel(name="tokens", peer=InfrahubKind.ACCOUNTTOKEN, optional=True, cardinality=Cardinality.MANY)],
)
