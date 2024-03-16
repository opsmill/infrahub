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
    VALIDATE_CONSTRAINT = "validate_constraint"
    NOT_APPLICABLE = "not_applicable"


class UpdateValidationErrorType(Enum):
    NOT_SUPPORTED = "not_supported"
    VALIDATOR_FAILED = "validator_failed"
    MIGRATION_NOT_AVAILABLE = "migration_not_available"
    VALIDATOR_NOT_AVAILABLE = "validator_not_available"
