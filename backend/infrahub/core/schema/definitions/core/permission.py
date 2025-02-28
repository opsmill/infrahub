from infrahub.core.constants import (
    AllowOverrideType,
    BranchSupportType,
    GlobalPermissions,
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
)

core_base_permission = {
    "name": "BasePermission",
    "namespace": "Core",
    "description": "A permission grants right to an account",
    "label": "Base permission",
    "icon": "mdi:user-key",
    "include_in_menu": False,
    "generate_profile": False,
    "attributes": [
        {"name": "description", "kind": "Text", "optional": True},
        {
            "name": "identifier",
            "kind": "Text",
            "read_only": True,
            "optional": True,
            "allow_override": AllowOverrideType.NONE,
        },
    ],
    "relationships": [
        {
            "name": "roles",
            "peer": InfrahubKind.ACCOUNTROLE,
            "optional": True,
            "identifier": "role__permissions",
            "cardinality": "many",
            "kind": "Attribute",
        }
    ],
}

core_object_permission = {
    "name": "ObjectPermission",
    "namespace": "Core",
    "description": "A permission that grants rights to perform actions on objects",
    "label": "Object permission",
    "include_in_menu": False,
    "order_by": ["namespace__value", "name__value", "action__value", "decision__value"],
    "display_labels": ["namespace__value", "name__value", "action__value", "decision__value"],
    "human_friendly_id": ["namespace__value", "name__value", "action__value", "decision__value"],
    "uniqueness_constraints": [["namespace__value", "name__value", "action__value", "decision__value"]],
    "generate_profile": False,
    "inherit_from": [InfrahubKind.BASEPERMISSION],
    "attributes": [
        {"name": "namespace", "kind": "Text", "order_weight": 2000},
        {"name": "name", "kind": "Text", "order_weight": 3000},
        {
            "name": "action",
            "kind": "Text",
            "enum": PermissionAction.available_types(),
            "default_value": PermissionAction.ANY.value,
            "order_weight": 4000,
        },
        {
            "name": "decision",
            "kind": "Number",
            "enum": PermissionDecision.available_types(),
            "default_value": PermissionDecision.ALLOW_ALL.value,
            "order_weight": 5000,
            "description": (
                "Decide to deny or allow the action. If allowed, it can be configured for the default branch, any other branches or all "
                "branches"
            ),
        },
    ],
}

core_global_permission = {
    "name": "GlobalPermission",
    "namespace": "Core",
    "description": "A permission that grants global rights to perform actions in Infrahub",
    "label": "Global permission",
    "include_in_menu": False,
    "order_by": ["action__value", "decision__value"],
    "display_labels": ["action__value", "decision__value"],
    "human_friendly_id": ["action__value", "decision__value"],
    "generate_profile": False,
    "inherit_from": [InfrahubKind.BASEPERMISSION],
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {
            "name": "action",
            "kind": "Dropdown",
            "choices": [{"name": permission.value} for permission in GlobalPermissions],
            "order_weight": 2000,
        },
        {
            "name": "decision",
            "kind": "Number",
            "enum": PermissionDecision.available_types(),
            "default_value": PermissionDecision.ALLOW_ALL.value,
            "order_weight": 3000,
            "description": "Decide to deny or allow the action at a global level",
        },
    ],
}

core_account_role = {
    "name": "AccountRole",
    "namespace": "Core",
    "description": "A role defines a set of permissions to grant to a group of accounts",
    "label": "Account role",
    "icon": "mdi:user-badge",
    "include_in_menu": False,
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "human_friendly_id": ["name__value"],
    "generate_profile": False,
    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
    "relationships": [
        {
            "name": "groups",
            "peer": InfrahubKind.ACCOUNTGROUP,
            "optional": True,
            "identifier": "role__accountgroups",
            "cardinality": "many",
            "kind": "Attribute",
        },
        {
            "name": "permissions",
            "peer": InfrahubKind.BASEPERMISSION,
            "optional": True,
            "identifier": "role__permissions",
            "cardinality": "many",
            "kind": "Attribute",
        },
    ],
}

core_account_group = {
    "name": "AccountGroup",
    "namespace": "Core",
    "description": "A group of users to manage common permissions",
    "label": "Account group",
    "icon": "mdi:account-group",
    "include_in_menu": False,
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "human_friendly_id": ["name__value"],
    "generate_profile": False,
    "inherit_from": [InfrahubKind.LINEAGEOWNER, InfrahubKind.LINEAGESOURCE, InfrahubKind.GENERICGROUP],
    "branch": BranchSupportType.AGNOSTIC.value,
    "relationships": [
        {
            "name": "roles",
            "peer": InfrahubKind.ACCOUNTROLE,
            "optional": True,
            "identifier": "role__accountgroups",
            "cardinality": "many",
            "kind": "Attribute",
        }
    ],
}
