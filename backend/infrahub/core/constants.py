import enum


class PermissionLevel(enum.Flag):
    READ = 1

    WRITE = 2

    ADMIN = 3

    DEFAULT = 0


class DiffAction(str, enum.Enum):
    ADDED = "added"

    REMOVED = "removed"

    UPDATED = "updated"

    UNCHANGED = "unchanged"


class RelationshipStatus(str, enum.Enum):
    ACTIVE = "active"

    DELETED = "deleted"
