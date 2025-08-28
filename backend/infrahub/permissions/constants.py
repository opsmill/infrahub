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
    GlobalPermissions.REVIEW_PROPOSED_CHANGE.value: "You are not allowed to review proposed changes",
    GlobalPermissions.MANAGE_SCHEMA.value: "You are not allowed to manage the schema",
    GlobalPermissions.MANAGE_ACCOUNTS.value: "You are not allowed to manage user accounts, groups or roles",
    GlobalPermissions.MANAGE_PERMISSIONS.value: "You are not allowed to manage permissions",
    GlobalPermissions.MANAGE_REPOSITORIES.value: "You are not allowed to manage repositories",
}

GLOBAL_PERMISSION_DESCRIPTION = {
    GlobalPermissions.EDIT_DEFAULT_BRANCH: "Allow a user to change data in the default branch",
    GlobalPermissions.MERGE_BRANCH: "Allow a user to merge branches",
    GlobalPermissions.MERGE_PROPOSED_CHANGE: "Allow a user to merge proposed changes",
    GlobalPermissions.REVIEW_PROPOSED_CHANGE: "Allow a user to approve or reject proposed changes",
    GlobalPermissions.MANAGE_SCHEMA: "Allow a user to manage the schema",
    GlobalPermissions.MANAGE_ACCOUNTS: "Allow a user to manage accounts, account roles and account groups",
    GlobalPermissions.MANAGE_PERMISSIONS: "Allow a user to manage permissions",
    GlobalPermissions.MANAGE_REPOSITORIES: "Allow a user to manage repositories",
    GlobalPermissions.SUPER_ADMIN: "Allow a user to do anything",
}
