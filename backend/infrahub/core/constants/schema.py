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
