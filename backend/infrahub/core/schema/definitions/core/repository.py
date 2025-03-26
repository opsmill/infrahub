from infrahub.core.constants import (
    AllowOverrideType,
    BranchSupportType,
    InfrahubKind,
    RepositoryInternalStatus,
    RepositoryOperationalStatus,
    RepositorySyncStatus,
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
    display_labels=["name__value"],
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
            default_value="main",
            order_weight=6000,
        ),
        Attr(
            name="commit",
            kind="Text",
            optional=True,
            branch=BranchSupportType.LOCAL,
            order_weight=7000,
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
    display_labels=["name__value"],
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
            default_value="main",
            branch=BranchSupportType.AWARE,
            order_weight=6000,
        ),
        Attr(
            name="commit",
            kind="Text",
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
    display_labels=["name__value"],
    icon="mdi:source-repository",
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"], ["location__value"]],
    documentation="/topics/repository",
    attributes=[
        Attr(
            name="name",
            regex=r"^[^/]*$",
            kind="Text",
            unique=True,
            branch=BranchSupportType.AGNOSTIC,
            order_weight=1000,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="description",
            kind="Text",
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
            order_weight=2000,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="location",
            kind="Text",
            unique=True,
            branch=BranchSupportType.AGNOSTIC,
            order_weight=3000,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="internal_status",
            kind="Dropdown",
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
            name="sync_status",
            kind="Dropdown",
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
            order_weight=10000,
        ),
        Rel(
            name="queries",
            peer=InfrahubKind.GRAPHQLQUERY,
            identifier="graphql_query__repository",
            optional=True,
            cardinality=Cardinality.MANY,
            order_weight=9000,
        ),
        Rel(
            name="checks",
            peer=InfrahubKind.CHECKDEFINITION,
            identifier="check_definition__repository",
            optional=True,
            cardinality=Cardinality.MANY,
            order_weight=11000,
        ),
        Rel(
            name="generators",
            peer=InfrahubKind.GENERATORDEFINITION,
            identifier="generator_definition__repository",
            optional=True,
            cardinality=Cardinality.MANY,
            order_weight=12000,
        ),
    ],
)
