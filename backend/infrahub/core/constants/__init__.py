from __future__ import annotations

import enum

from infrahub.core.constants import infrahubkind as InfrahubKind
from infrahub.exceptions import ValidationError
from infrahub.utils import InfrahubStringEnum

from .schema import FlagProperty, NodeProperty, SchemaElementPathType, UpdateSupport, UpdateValidationErrorType

__all__ = [
    "InfrahubKind",
    "FlagProperty",
    "NodeProperty",
    "UpdateSupport",
    "UpdateValidationErrorType",
    "SchemaElementPathType",
]


GLOBAL_BRANCH_NAME = "-global-"

DEFAULT_IP_NAMESPACE = "default"

RESERVED_BRANCH_NAMES = [GLOBAL_BRANCH_NAME]

RESERVED_ATTR_REL_NAMES = [
    "any",
    "attribute",
    "attributes",
    "attr",
    "attrs",
    "relationship",
    "relationships",
    "rel",
    "rels",
    "save",
    "hfid",
]

RESERVED_ATTR_GEN_NAMES = ["type"]

NULL_VALUE = "NULL"


class PermissionLevel(enum.Flag):
    READ = 1
    WRITE = 2
    ADMIN = 3
    DEFAULT = 0


class AccountRole(InfrahubStringEnum):
    ADMIN = "admin"
    READ_ONLY = "read-only"
    READ_WRITE = "read-write"


class AccountType(InfrahubStringEnum):
    USER = "User"
    SCRIPT = "Script"
    BOT = "Bot"
    Git = "Git"


class AccountStatus(InfrahubStringEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ArtifactStatus(InfrahubStringEnum):
    ERROR = "Error"
    PENDING = "Pending"
    PROCESSING = "Processing"
    READY = "Ready"


class BranchSupportType(InfrahubStringEnum):
    AWARE = "aware"
    AGNOSTIC = "agnostic"
    LOCAL = "local"


class BranchConflictKeep(InfrahubStringEnum):
    TARGET = "target"
    SOURCE = "source"


class AllowOverrideType(InfrahubStringEnum):
    NONE = "none"
    ANY = "any"


class ContentType(InfrahubStringEnum):
    APPLICATION_JSON = "application/json"
    TEXT_PLAIN = "text/plain"


class CheckType(InfrahubStringEnum):
    ARTIFACT = "artifact"
    DATA = "data"
    GENERATOR = "generator"
    REPOSITORY = "repository"
    SCHEMA = "schema"
    TEST = "test"
    USER = "user"
    ALL = "all"


class RepositoryInternalStatus(InfrahubStringEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    STAGING = "staging"


class RepositorySyncStatus(InfrahubStringEnum):
    UNKNOWN = "unknown"
    IN_SYNC = "in-sync"
    ERROR_IMPORT = "error-import"
    SYNCING = "syncing"


class RepositoryOperationalStatus(InfrahubStringEnum):
    UNKNOWN = "unknown"
    ERROR_CRED = "error-cred"
    ERROR_CONNECTION = "error-connection"
    ERROR = "error"
    ONLINE = "online"


class DiffAction(InfrahubStringEnum):
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class GeneratorInstanceStatus(InfrahubStringEnum):
    ERROR = "Error"
    PENDING = "Pending"
    PROCESSING = "Processing"
    READY = "Ready"


class MutationAction(InfrahubStringEnum):
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"
    UNDEFINED = "undefined"


class PathResourceType(InfrahubStringEnum):
    SCHEMA = "schema"
    DATA = "data"
    FILE = "file"


class SchemaPathType(InfrahubStringEnum):
    NODE = "node"
    ATTRIBUTE = "attribute"
    RELATIONSHIP = "relationship"


class PathType(InfrahubStringEnum):
    NODE = "node"
    ATTRIBUTE = "attribute"
    RELATIONSHIP_ONE = "relationship_one"
    RELATIONSHIP_MANY = "relationship_many"

    @classmethod
    def from_relationship(cls, relationship: RelationshipCardinality) -> PathType:
        if relationship == RelationshipCardinality.ONE:
            return cls("relationship_one")

        return cls("relationship_many")


class FilterSchemaKind(InfrahubStringEnum):
    TEXT = "Text"
    LIST = "Text"
    NUMBER = "Number"
    BOOLEAN = "Boolean"
    OBJECT = "Object"
    MULTIOBJECT = "MultiObject"
    ENUM = "Enum"


class ProposedChangeState(InfrahubStringEnum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
    CANCELED = "canceled"

    def validate_state_check_run(self) -> None:
        if self == ProposedChangeState.OPEN:
            return

        raise ValidationError(input_value="Unable to trigger check on proposed changes that aren't in the open state")

    def validate_editability(self) -> None:
        if self in [ProposedChangeState.CANCELED, ProposedChangeState.MERGED]:
            raise ValidationError(
                input_value=f"A proposed change in the {self.value} state is not allowed to be updated"
            )

    def validate_state_transition(self, updated_state: ProposedChangeState) -> None:
        if self == ProposedChangeState.OPEN:
            return

        if self == ProposedChangeState.CLOSED and updated_state not in [
            ProposedChangeState.CANCELED,
            ProposedChangeState.OPEN,
        ]:
            raise ValidationError(
                input_value="A closed proposed change is only allowed to transition to the open state"
            )


class HashableModelState(InfrahubStringEnum):
    PRESENT = "present"
    ABSENT = "absent"


class RelationshipCardinality(InfrahubStringEnum):
    ONE = "one"
    MANY = "many"


class RelationshipKind(InfrahubStringEnum):
    GENERIC = "Generic"
    ATTRIBUTE = "Attribute"
    COMPONENT = "Component"
    PARENT = "Parent"
    GROUP = "Group"
    HIERARCHY = "Hierarchy"
    PROFILE = "Profile"


class RelationshipStatus(InfrahubStringEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class RelationshipDirection(InfrahubStringEnum):
    BIDIR = "bidirectional"
    OUTBOUND = "outbound"
    INBOUND = "inbound"

    @property
    def neighbor_direction(self) -> RelationshipDirection:
        NEIGHBOR_MAP = {
            RelationshipDirection.BIDIR: RelationshipDirection.BIDIR,
            RelationshipDirection.INBOUND: RelationshipDirection.OUTBOUND,
            RelationshipDirection.OUTBOUND: RelationshipDirection.INBOUND,
        }
        return NEIGHBOR_MAP[self]


class RelationshipHierarchyDirection(InfrahubStringEnum):
    ANCESTORS = "ancestors"
    DESCENDANTS = "descendants"


class RelationshipDeleteBehavior(InfrahubStringEnum):
    NO_ACTION = "no-action"
    CASCADE = "cascade"


class Severity(InfrahubStringEnum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TaskConclusion(InfrahubStringEnum):
    UNKNOWN = "unknown"
    FAILURE = "failure"
    SUCCESS = "success"


class ValidatorConclusion(InfrahubStringEnum):
    UNKNOWN = "unknown"
    FAILURE = "failure"
    SUCCESS = "success"


class ValidatorState(InfrahubStringEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class AttributeDBNodeType(InfrahubStringEnum):
    DEFAULT = "default"
    IPHOST = "iphost"
    IPNETWORK = "ipnetwork"


RESTRICTED_NAMESPACES: list[str] = [
    "Account",
    "Branch",
    # "Builtin",
    "Core",
    "Deprecated",
    "Diff",
    "Infrahub",
    "Internal",
    "Lineage",
    "Schema",
    "Profile",
]

NODE_NAME_REGEX = r"^[A-Z][a-zA-Z0-9]+$"
DEFAULT_NAME_MIN_LENGTH = 2
NAME_REGEX = r"^[a-z0-9\_]+$"
DEFAULT_DESCRIPTION_LENGTH = 128

DEFAULT_NAME_MAX_LENGTH = 32
DEFAULT_LABEL_MAX_LENGTH = 64
DEFAULT_KIND_MIN_LENGTH = 3
DEFAULT_KIND_MAX_LENGTH = 32
NAMESPACE_REGEX = r"^[A-Z][a-z0-9]+$"
NODE_KIND_REGEX = r"^[A-Z][a-zA-Z0-9]+$"
DEFAULT_REL_IDENTIFIER_LENGTH = 128
