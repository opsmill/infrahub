from __future__ import annotations

from enum import IntFlag, StrEnum, auto

from infrahub.core.constants import GlobalPermissions


class PermissionDecisionFlag(IntFlag):
    DENY = 1
    ALLOW_DEFAULT = 2
    ALLOW_OTHER = 4
    ALLOW_ALL = ALLOW_DEFAULT | ALLOW_OTHER


class BranchRelativePermissionDecision(StrEnum):
    """This enum is only used to communicate a permission decision relative to a branch."""

    DENY = auto()
    ALLOW = auto()
    ALLOW_DEFAULT = auto()
    ALLOW_OTHER = auto()


GLOBAL_PERMISSION_DENIAL_MESSAGE = {
    GlobalPermissions.EDIT_DEFAULT_BRANCH.value: "You are not allowed to change data in the default branch",
    GlobalPermissions.MERGE_BRANCH.value: "You are not allowed to merge a branch",
    GlobalPermissions.MERGE_PROPOSED_CHANGE.value: "You are not allowed to merge proposed changes",
    GlobalPermissions.MANAGE_SCHEMA.value: "You are not allowed to manage the schema",
    GlobalPermissions.MANAGE_ACCOUNTS.value: "You are not allowed to manage user accounts, groups or roles",
    GlobalPermissions.MANAGE_PERMISSIONS.value: "You are not allowed to manage permissions",
    GlobalPermissions.MANAGE_REPOSITORIES.value: "You are not allowed to manage repositories",
}
