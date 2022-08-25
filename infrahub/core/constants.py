import enum


class PermissionLevel(enum.Flag):

    READ = 1

    WRITE = 2

    ADMIN = 3

    DEFAULT = 0


class RelationshipStatus(enum.Flag):

    ACTIVE = "active"

    DELETED = "deleted"
