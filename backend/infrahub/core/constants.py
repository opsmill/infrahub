import enum

from infrahub.utils import InfrahubNumberEnum, InfrahubStringEnum

GLOBAL_BRANCH_NAME = "-global-"

RESERVED_BRANCH_NAMES = [GLOBAL_BRANCH_NAME]


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


class ArtifactStatus(InfrahubStringEnum):
    ERROR = "Error"
    PENDING = "Pending"
    PROCESSING = "Processing"
    READY = "Ready"


class BranchSupportType(InfrahubStringEnum):
    AWARE = "aware"
    AGNOSTIC = "agnostic"


class ContentType(InfrahubStringEnum):
    APPLICATION_JSON = "application/json"
    TEXT_PLAIN = "text/plain"


class CriticalityLevel(InfrahubNumberEnum):
    one = 1
    two = 2
    three = 3
    four = 4
    five = 5
    six = 6
    seven = 7
    eight = 8
    nine = 9
    ten = 1


class DiffAction(InfrahubStringEnum):
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class FilterSchemaKind(InfrahubStringEnum):
    TEXT = "Text"
    LIST = "Text"
    NUMBER = "Number"
    BOOLEAN = "Boolean"
    OBJECT = "Object"
    MULTIOBJECT = "MultiObject"
    ENUM = "Enum"


class RelationshipCardinality(InfrahubStringEnum):
    ONE = "one"
    MANY = "many"


class RelationshipKind(InfrahubStringEnum):
    GENERIC = "Generic"
    ATTRIBUTE = "Attribute"
    COMPONENT = "Component"
    PARENT = "Parent"
    GROUP = "Group"


class RelationshipStatus(InfrahubStringEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class ValidatorConclusion(InfrahubStringEnum):
    UNKNOWN = "unknown"
    FAILURE = "failure"
    SUCCESS = "success"


class ValidatorState(InfrahubStringEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
