from enum import Enum, Flag, auto


class FlagProperty(Enum):
    IS_VISIBLE = "is_visible"
    IS_PROTECTED = "is_protected"


class NodeProperty(Enum):
    SOURCE = "source"
    OWNER = "owner"


class UpdateSupport(Enum):
    NOT_SUPPORTED = "not_supported"
    ALLOWED = "allowed"
    MIGRATION_REQUIRED = "migration_required"
    VALIDATE_CONSTRAINT = "validate_constraint"
    NOT_APPLICABLE = "not_applicable"


class UpdateValidationErrorType(Enum):
    NOT_SUPPORTED = "not_supported"
    VALIDATOR_FAILED = "validator_failed"
    MIGRATION_NOT_AVAILABLE = "migration_not_available"
    VALIDATOR_NOT_AVAILABLE = "validator_not_available"


class SchemaElementPathType(Flag):
    ATTR = auto()
    REL_ONE_NO_ATTR = auto()
    REL_ONE_ATTR = auto()
    REL_MANY_NO_ATTR = auto()
    REL_MANY_ATTR = auto()
    ALL_RELS = REL_ONE_NO_ATTR | REL_MANY_NO_ATTR | REL_ONE_ATTR | REL_MANY_ATTR
    RELS_ATTR = REL_ONE_ATTR | REL_MANY_ATTR
    RELS_NO_ATTR = REL_ONE_NO_ATTR | REL_MANY_NO_ATTR
    REL_ONE = REL_ONE_NO_ATTR | REL_ONE_ATTR
    REL_MANY = REL_MANY_NO_ATTR | REL_MANY_ATTR
