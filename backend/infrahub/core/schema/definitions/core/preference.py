from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_global_preference = NodeSchema(
    name="GlobalPreference",
    namespace="Core",
    description="Organisation-wide defaults applied to every user unless overridden.",
    label="Global Preference",
    icon="mdi:cog",
    include_in_menu=False,
    generate_profile=False,
    display_label="{{ 'Global Preferences' }}",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(
            name="date_format",
            kind="Text",
            optional=True,
            order_weight=1000,
            description='date-fns pattern string (e.g. "dd/MM/yyyy", "yyyy-MM-dd HH:mm"). Literal "relative" renders relative time.',
        ),
        Attr(
            name="timezone",
            kind="Text",
            optional=True,
            order_weight=1100,
            description="IANA timezone name (e.g. Europe/Paris, UTC). Unset means the browser-resolved timezone.",
        ),
    ],
)

core_user_preference = NodeSchema(
    name="UserPreference",
    namespace="Core",
    description="Per-user overrides of global preferences.",
    label="User Preference",
    icon="mdi:account-cog-outline",
    include_in_menu=False,
    generate_profile=False,
    display_label="Preferences of {{ account__name__value }}",
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["account"]],
    attributes=[
        Attr(
            name="date_format",
            kind="Text",
            optional=True,
            order_weight=1000,
            description="User override of the global date_format. Same semantics as CoreGlobalPreference.date_format.",
        ),
        Attr(
            name="timezone",
            kind="Text",
            optional=True,
            order_weight=1100,
            description="User override of the global timezone. Same semantics as CoreGlobalPreference.timezone.",
        ),
    ],
    relationships=[
        Rel(
            name="account",
            peer=InfrahubKind.GENERICACCOUNT,
            identifier="account__preferences",
            kind=RelKind.PARENT,
            cardinality=Cardinality.ONE,
            optional=False,
            on_delete=RelationshipDeleteBehavior.CASCADE,
            order_weight=100,
        ),
    ],
)
