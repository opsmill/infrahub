from infrahub.core.constants import (
    BranchSupportType,
    RelationshipCardinality,
    RelationshipDeleteBehavior,
    RelationshipKind,
)
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot

RELATIONSHIP_IDENTIFIER = "agnosticretire_widget__agnosticretire_gadget"

WIDGET_KIND = "AgnosticretireWidget"
GADGET_KIND = "AgnosticretireGadget"
BEACON_KIND = "AgnosticretireBeacon"

AGNOSTIC_WIDGET = NodeSchema(
    name="Widget",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="serial", kind="Number", branch=BranchSupportType.AGNOSTIC),
    ],
    relationships=[
        RelationshipSchema(
            name="gadget",
            kind=RelationshipKind.GENERIC,
            peer=GADGET_KIND,
            identifier=RELATIONSHIP_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

AGNOSTIC_GADGET = NodeSchema(
    name="Gadget",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

# A kind that is itself branch-agnostic, so its own existence edge lives on the global branch.
AGNOSTIC_BEACON = NodeSchema(
    name="Beacon",
    namespace="Agnosticretire",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="serial", kind="Number", optional=True),
    ],
)

AGNOSTIC_RETIREMENT_SCHEMA = SchemaRoot(nodes=[AGNOSTIC_WIDGET, AGNOSTIC_GADGET, AGNOSTIC_BEACON])

TEAM_KIND = "AgnosticretireTeam"
MEMBER_KIND = "AgnosticretireMember"
BADGE_KIND = "AgnosticretireBadge"
CERTIFICATE_KIND = "AgnosticretireCertificate"
STICKER_KIND = "AgnosticretireSticker"
HOLDER_KIND = "AgnosticretireHolder"

# Branch-agnostic, so deleting a team removes it on every branch at once.
AGNOSTIC_TEAM = NodeSchema(
    name="Team",
    namespace="Agnosticretire",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="members",
            peer=MEMBER_KIND,
            identifier="agnosticretire_member__agnosticretire_team",
            cardinality=RelationshipCardinality.MANY,
            optional=True,
        ),
        RelationshipSchema(
            name="badges",
            peer=BADGE_KIND,
            identifier="agnosticretire_badge__agnosticretire_team",
            cardinality=RelationshipCardinality.MANY,
            optional=True,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
        RelationshipSchema(
            name="certificates",
            peer=CERTIFICATE_KIND,
            identifier="agnosticretire_certificate__agnosticretire_team",
            cardinality=RelationshipCardinality.MANY,
            optional=True,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
        RelationshipSchema(
            name="stickers",
            peer=STICKER_KIND,
            identifier="agnosticretire_sticker__agnosticretire_team",
            cardinality=RelationshipCardinality.MANY,
            optional=True,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
    ],
)

AGNOSTIC_MEMBER = NodeSchema(
    name="Member",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="team",
            peer=TEAM_KIND,
            identifier="agnosticretire_member__agnosticretire_team",
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)

# A cascade target whose relationship back to its team is optional.
AGNOSTIC_BADGE = NodeSchema(
    name="Badge",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="team",
            peer=TEAM_KIND,
            identifier="agnosticretire_badge__agnosticretire_team",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
    ],
)

# A cascade target whose relationship back to its team is required.
AGNOSTIC_CERTIFICATE = NodeSchema(
    name="Certificate",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="team",
            peer=TEAM_KIND,
            identifier="agnosticretire_certificate__agnosticretire_team",
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)

# A cascade target that does not declare the relationship back to its team.
AGNOSTIC_STICKER = NodeSchema(
    name="Sticker",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

# Requires a badge, which is branch-aware, so deleting a team removes the badge on the request branch only.
AGNOSTIC_HOLDER = NodeSchema(
    name="Holder",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="badge",
            peer=BADGE_KIND,
            identifier="agnosticretire_badge__agnosticretire_holder",
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)

AGNOSTIC_DELETE_SCHEMA = SchemaRoot(
    nodes=[AGNOSTIC_TEAM, AGNOSTIC_MEMBER, AGNOSTIC_BADGE, AGNOSTIC_CERTIFICATE, AGNOSTIC_STICKER, AGNOSTIC_HOLDER]
)

ROSTER_KIND = "AgnosticretireRoster"
GUARDIAN_KIND = "AgnosticretireGuardian"

# Branch-aware, and cascades to branch-agnostic teams.
AGNOSTIC_ROSTER = NodeSchema(
    name="Roster",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="teams",
            peer=TEAM_KIND,
            identifier="agnosticretire_roster__agnosticretire_team",
            cardinality=RelationshipCardinality.MANY,
            optional=True,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
    ],
)

AGNOSTIC_ROSTER_SCHEMA = SchemaRoot(nodes=[AGNOSTIC_ROSTER])

# Loaded on one branch only, so its required relationship to a team exists in that branch's schema only.
AGNOSTIC_GUARDIAN = NodeSchema(
    name="Guardian",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="team",
            peer=TEAM_KIND,
            identifier="agnosticretire_guardian__agnosticretire_team",
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)

AGNOSTIC_GUARDIAN_SCHEMA = SchemaRoot(nodes=[AGNOSTIC_GUARDIAN])
