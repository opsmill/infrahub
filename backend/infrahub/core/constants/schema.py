from enum import Enum


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
    CHECK_CONSTRAINTS = "check_constraints"
    NA = "not_applicable"


class UpdateValidationErrorType(Enum):
    NOT_SUPPORTED = "not_supported"
    CHECK_FAILED = "check_failed"
    MIGRATION_NOT_AVAILABLE = "migration_not_available"
    CHECK_NOT_AVAILABLE = "check_not_available"
