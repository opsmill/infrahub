from infrahub.core.constants import (
    AllowOverrideType,
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
    RepositoryDeliveryFailureCause,
    RepositoryDeliveryStatus,
    RepositoryInternalStatus,
    RepositoryOperationalStatus,
    RepositorySyncStatus,
    SchemaAttributeDisplay,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...dropdown import DropdownChoice
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_repository = NodeSchema(
    name="Repository",
    namespace="Core",
    description="A Git Repository integrated with Infrahub",
    include_in_menu=False,
    icon="mdi:source-repository",
    label="Repository",
    default_filter="name__value",
    order_by=["name__value"],
    display_label="name__value",
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[
        InfrahubKind.LINEAGEOWNER,
        InfrahubKind.LINEAGESOURCE,
        InfrahubKind.GENERICREPOSITORY,
        InfrahubKind.TASKTARGET,
    ],
    documentation="/topics/repository",
    attributes=[
        Attr(
            name="default_branch",
            kind="Text",
            description="Remote branch that Infrahub maps onto its own default branch. Need not be the remote default branch.",
            default_value="main",
            order_weight=6000,
        ),
        Attr(
            name="commit",
            kind="Text",
            description="Current commit hash being tracked",
            optional=True,
            branch=BranchSupportType.LOCAL,
            order_weight=7000,
        ),
        Attr(
            name="delivery_status",
            kind="Dropdown",
            label="Push to remote",
            description=(
                "Whether merged changes wait to be pushed to the remote, and whether a user must act. "
                "Live on the default branch only."
            ),
            choices=[
                DropdownChoice(
                    name=RepositoryDeliveryStatus.NONE.value,
                    label="Nothing pending",
                    description="No merged change waits to be pushed to the remote.",
                    color="#9ca3af",
                ),
                DropdownChoice(
                    name=RepositoryDeliveryStatus.PENDING.value,
                    label="Pending",
                    description="A push runs, a push is about to run, or an automatic retry waits.",
                    color="#60a5fa",
                ),
                DropdownChoice(
                    name=RepositoryDeliveryStatus.ACTION_REQUIRED.value,
                    label="Action required",
                    description="No automatic push will run. A user must act.",
                    color="#f87171",
                ),
            ],
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6100,
        ),
        Attr(
            name="delivery_failure_cause",
            kind="Dropdown",
            label="Push failure cause",
            description=(
                "Why the last push to the remote, or the import that follows it, failed. "
                "Live on the default branch only."
            ),
            choices=[
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE.value, label="Remote unreachable"
                ),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.REMOTE_ADVANCED.value, label="Remote moved during the push"
                ),
                DropdownChoice(name=RepositoryDeliveryFailureCause.RECORD_FAILED.value, label="Pushed, not recorded"),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.NOT_FOUND.value, label="Repository not found on the remote"
                ),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.CERTIFICATE.value, label="Certificate verification failed"
                ),
                DropdownChoice(name=RepositoryDeliveryFailureCause.CREDENTIALS.value, label="Credentials rejected"),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.PERMISSION.value, label="Push refused by the remote"
                ),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED.value,
                    label="Import of the delivered commit was interrupted",
                ),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.IMPORT_FAILED.value,
                    label="Import of the delivered commit failed",
                ),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.REPLAY_CONFLICT.value,
                    label="A pending merge conflicts with the remote",
                ),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.SOURCE_DISCARDED.value,
                    label="A source commit is no longer on the remote",
                ),
                DropdownChoice(
                    name=RepositoryDeliveryFailureCause.DESTINATION_REWRITTEN.value,
                    label="The remote branch history was rewritten",
                ),
                DropdownChoice(name=RepositoryDeliveryFailureCause.UNCLASSIFIED.value, label="Unclassified failure"),
            ],
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6200,
        ),
        Attr(
            name="delivery_error",
            kind="TextArea",
            label="Push error",
            description=(
                "Message of the last failure to push or import, with credentials removed. "
                "Live on the default branch only."
            ),
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6300,
        ),
        Attr(
            name="delivery_queue",
            kind="JSON",
            label="Pending pushes",
            description=(
                "Merged changes that wait to be pushed to the remote, in merge order. Live on the default branch only."
            ),
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6400,
        ),
        Attr(
            name="delivery_held_regeneration",
            kind="JSON",
            label="Held regeneration",
            description=(
                "Definitions and Python computed attributes held until the pending pushes reach the remote. "
                "Live on the default branch only."
            ),
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6500,
        ),
        Attr(
            name="delivery_last_abandonment",
            kind="JSON",
            label="Last abandoned push",
            description=(
                "Who abandoned the last pending pushes, when, and which merged changes were dropped. "
                "Live on the default branch only."
            ),
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6600,
        ),
        Attr(
            name="delivery_last_delivered_commit",
            kind="Text",
            label="Last pushed commit",
            description="Commit of the last push that reached the remote. Live on the default branch only.",
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6700,
        ),
        Attr(
            name="delivery_reverted",
            kind="JSON",
            label="Reverted push",
            description=(
                "A pushed commit that a rewrite of the remote branch history discarded. "
                "Live on the default branch only."
            ),
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6800,
        ),
        Attr(
            name="delivery_progress",
            kind="JSON",
            label="Push progress",
            description=(
                "Times when the push attempt started and last moved, and when the next automatic retry is due. "
                "Live on the default branch only."
            ),
            optional=True,
            read_only=True,
            branch=BranchSupportType.LOCAL,
            display=SchemaAttributeDisplay.EXTRA,
            allow_override=AllowOverrideType.NONE,
            order_weight=6900,
        ),
    ],
)

core_read_only_repository = NodeSchema(
    name="ReadOnlyRepository",
    namespace="Core",
    description="A Git Repository integrated with Infrahub, Git-side will not be updated",
    include_in_menu=False,
    label="Read-Only Repository",
    default_filter="name__value",
    order_by=["name__value"],
    display_label="name__value",
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[
        InfrahubKind.LINEAGEOWNER,
        InfrahubKind.LINEAGESOURCE,
        InfrahubKind.GENERICREPOSITORY,
        InfrahubKind.TASKTARGET,
    ],
    documentation="/topics/repository",
    attributes=[
        Attr(
            name="ref",
            kind="Text",
            description="Git reference (branch or tag) to track",
            default_value="main",
            branch=BranchSupportType.AWARE,
            order_weight=6000,
        ),
        Attr(
            name="commit",
            kind="Text",
            description="Current commit hash being tracked",
            optional=True,
            branch=BranchSupportType.AWARE,
            order_weight=7000,
        ),
    ],
)

core_generic_repository = GenericSchema(
    name="GenericRepository",
    namespace="Core",
    label="Git Repository",
    description="A Git Repository integrated with Infrahub",
    include_in_menu=False,
    default_filter="name__value",
    order_by=["name__value"],
    display_label="name__value",
    icon="mdi:source-repository",
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"], ["location__value"]],
    documentation="/topics/repository",
    restricted_namespaces=["Core"],
    attributes=[
        Attr(
            name="name",
            regex=r"^[^/]*$",
            kind="Text",
            description="Unique name identifier for the repository",
            unique=True,
            branch=BranchSupportType.AGNOSTIC,
            order_weight=1000,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="description",
            kind="Text",
            description="Description of the repository",
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
            order_weight=2000,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="location",
            kind="Text",
            description="URL or path to the Git repository",
            unique=True,
            branch=BranchSupportType.AGNOSTIC,
            order_weight=3000,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="internal_status",
            kind="Dropdown",
            description="Internal status of the repository on this branch",
            choices=[
                DropdownChoice(
                    name=RepositoryInternalStatus.STAGING.value,
                    label="Staging",
                    description="Repository was recently added to this branch.",
                    color="#fef08a",
                ),
                DropdownChoice(
                    name=RepositoryInternalStatus.ACTIVE.value,
                    label="Active",
                    description="Repository is actively being synced for this branch",
                    color="#86efac",
                ),
                DropdownChoice(
                    name=RepositoryInternalStatus.INACTIVE.value,
                    label="Inactive",
                    description="Repository is not active on this branch.",
                    color="#e5e7eb",
                ),
            ],
            default_value="inactive",
            optional=False,
            branch=BranchSupportType.LOCAL,
            order_weight=7000,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="operational_status",
            kind="Dropdown",
            description="Connectivity status of the repository",
            choices=[
                DropdownChoice(
                    name=RepositoryOperationalStatus.UNKNOWN.value,
                    label="Unknown",
                    description="Status of the repository is unknown and mostlikely because it hasn't been synced yet",
                    color="#9ca3af",
                ),
                DropdownChoice(
                    name=RepositoryOperationalStatus.ONLINE.value,
                    label="Online",
                    description="Repository connection is working",
                    color="#86efac",
                ),
                DropdownChoice(
                    name=RepositoryOperationalStatus.ERROR_CRED.value,
                    label="Credential Error",
                    description="Repository can't be synced due to some credential error(s)",
                    color="#f87171",
                ),
                DropdownChoice(
                    name=RepositoryOperationalStatus.ERROR_CONNECTION.value,
                    label="Connectivity Error",
                    description="Repository can't be synced due to some connectivity error(s)",
                    color="#f87171",
                ),
                DropdownChoice(
                    name=RepositoryOperationalStatus.ERROR.value,
                    label="Error",
                    description="Repository can't be synced due to an unknown error",
                    color="#ef4444",
                ),
            ],
            optional=False,
            branch=BranchSupportType.AGNOSTIC,
            default_value=RepositoryOperationalStatus.UNKNOWN.value,
            order_weight=5000,
        ),
        Attr(
            name="commit",
            kind="Text",
            description="Current commit hash being tracked",
            optional=True,
            branch=BranchSupportType.LOCAL,
            order_weight=7500,
        ),
        Attr(
            name="sync_status",
            kind="Dropdown",
            description="Current synchronization status of the repository",
            choices=[
                DropdownChoice(
                    name=RepositorySyncStatus.UNKNOWN.value,
                    label="Unknown",
                    description="Status of the repository is unknown and mostlikely because it hasn't been synced yet",
                    color="#9ca3af",
                ),
                DropdownChoice(
                    name=RepositorySyncStatus.ERROR_IMPORT.value,
                    label="Import Error",
                    description="Repository import error observed",
                    color="#f87171",
                ),
                DropdownChoice(
                    name=RepositorySyncStatus.IN_SYNC.value,
                    label="In Sync",
                    description="The repository is syncing correctly",
                    color="#60a5fa",
                ),
                DropdownChoice(
                    name=RepositorySyncStatus.SYNCING.value,
                    label="Syncing",
                    description="A sync job is currently running against the repository.",
                    color="#a855f7",
                ),
            ],
            optional=False,
            branch=BranchSupportType.LOCAL,
            default_value=RepositorySyncStatus.UNKNOWN.value,
            order_weight=6000,
        ),
        Attr(
            name="last_rewrite_previous_commit",
            kind="Text",
            description="The commit Infrahub had imported on this branch before the last rewrite",
            optional=True,
            branch=BranchSupportType.LOCAL,
            order_weight=7600,
        ),
        Attr(
            name="last_rewrite_commit",
            kind="Text",
            description="The commit Infrahub moved this branch onto after the last rewrite",
            optional=True,
            branch=BranchSupportType.LOCAL,
            order_weight=7700,
        ),
        Attr(
            name="last_rewrite_at",
            kind="DateTime",
            description="When Infrahub detected the last rewrite of this branch",
            optional=True,
            branch=BranchSupportType.LOCAL,
            order_weight=7800,
        ),
        Attr(
            name="rewrite_count",
            kind="Number",
            description=(
                "How many rewrites this branch has seen, including those on the default branch before this branch "
                "was created"
            ),
            optional=True,
            branch=BranchSupportType.LOCAL,
            order_weight=7900,
        ),
    ],
    relationships=[
        Rel(
            name="credential",
            peer=InfrahubKind.CREDENTIAL,
            identifier="gitrepository__credential",
            kind=RelKind.ATTRIBUTE,
            optional=True,
            cardinality=Cardinality.ONE,
            order_weight=4000,
        ),
        Rel(
            name="tags",
            peer=InfrahubKind.TAG,
            kind=RelKind.ATTRIBUTE,
            optional=True,
            cardinality=Cardinality.MANY,
            order_weight=8000,
        ),
        Rel(
            name="transformations",
            peer=InfrahubKind.TRANSFORM,
            identifier="repository__transformation",
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
            order_weight=10000,
        ),
        Rel(
            name="queries",
            peer=InfrahubKind.GRAPHQLQUERY,
            identifier="graphql_query__repository",
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
            order_weight=9000,
        ),
        Rel(
            name="checks",
            peer=InfrahubKind.CHECKDEFINITION,
            identifier="check_definition__repository",
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
            order_weight=11000,
        ),
        Rel(
            name="generators",
            peer=InfrahubKind.GENERATORDEFINITION,
            identifier="generator_definition__repository",
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
            order_weight=12000,
        ),
        Rel(
            name="groups_objects",
            peer=InfrahubKind.REPOSITORYGROUP,
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
            order_weight=13000,
        ),
    ],
)
