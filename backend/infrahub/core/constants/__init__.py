from __future__ import annotations

import enum

from infrahub.core.constants import infrahubkind as InfrahubKind  # noqa: N812
from infrahub.exceptions import ValidationError
from infrahub.utils import InfrahubNumberEnum, InfrahubStringEnum

from .schema import FlagProperty, NodeProperty, SchemaElementPathType, UpdateSupport, UpdateValidationErrorType

__all__ = [
    "FlagProperty",
    "InfrahubKind",
    "NodeProperty",
    "SchemaElementPathType",
    "UpdateSupport",
    "UpdateValidationErrorType",
    "ValidationError",
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


class GlobalPermissions(InfrahubStringEnum):
    EDIT_DEFAULT_BRANCH = "edit_default_branch"
    SUPER_ADMIN = "super_admin"
    MERGE_BRANCH = "merge_branch"
    MERGE_PROPOSED_CHANGE = "merge_proposed_change"
    MANAGE_SCHEMA = "manage_schema"
    MANAGE_ACCOUNTS = "manage_accounts"
    MANAGE_PERMISSIONS = "manage_permissions"
    MANAGE_REPOSITORIES = "manage_repositories"


class PermissionAction(InfrahubStringEnum):
    ANY = "any"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"


class PermissionDecision(InfrahubNumberEnum):
    DENY = 1
    ALLOW_DEFAULT = 2
    ALLOW_OTHER = 4
    ALLOW_ALL = 6


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


class ComputedAttributeKind(InfrahubStringEnum):
    USER = "User"
    JINJA2 = "Jinja2"
    TRANSFORM_PYTHON = "TransformPython"


class BranchConflictKeep(InfrahubStringEnum):
    TARGET = "target"
    SOURCE = "source"


class AllowOverrideType(InfrahubStringEnum):
    NONE = "none"
    ANY = "any"


class ContentType(InfrahubStringEnum):
    APPLICATION_JSON = "application/json"
    APPLICATION_YAML = "application/yaml"
    APPLICATION_XML = "application/xml"
    TEXT_PLAIN = "text/plain"
    TEXT_MARKDOWN = "text/markdown"
    TEXT_CSV = "text/csv"
    IMAGE_SVG = "image/svg+xml"


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
