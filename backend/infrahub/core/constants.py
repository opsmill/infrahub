import enum


class PermissionLevel(enum.Flag):
    READ = 1

    WRITE = 2

    ADMIN = 3

    DEFAULT = 0


class DiffAction(enum.StrEnum):
    ADDED = "added"

    REMOVED = "removed"

    UPDATED = "updated"


class RelationshipStatus(enum.StrEnum):
    ACTIVE = "active"

    DELETED = "deleted"
