from infrahub.core.constants import (
    AccountStatus,
    AccountType,
    BranchSupportType,
    InfrahubKind,
)

core_account = {
    "name": "Account",
    "namespace": "Core",
    "description": "User Account for Infrahub",
    "include_in_menu": False,
    "label": "Account",
    "icon": "mdi:account",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["label__value"],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "inherit_from": [InfrahubKind.LINEAGEOWNER, InfrahubKind.LINEAGESOURCE, InfrahubKind.GENERICACCOUNT],
}

core_account_token = {
    "name": "AccountToken",
    "namespace": "Internal",
    "description": "Token for User Account",
    "include_in_menu": False,
    "label": "Account Token",
    "default_filter": "token__value",
    "display_labels": ["token__value"],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "uniqueness_constraints": [["token__value"]],
    "documentation": "/topics/auth",
    "attributes": [
        {"name": "name", "kind": "Text", "optional": True},
        {"name": "token", "kind": "Text", "unique": True},
        {"name": "expiration", "kind": "DateTime", "optional": True},
    ],
    "relationships": [
        {
            "name": "account",
            "peer": InfrahubKind.GENERICACCOUNT,
            "optional": False,
            "cardinality": "one",
            "identifier": "account__token",
        },
    ],
}

core_password_credential = {
    "name": "PasswordCredential",
    "namespace": "Core",
    "description": "Username/Password based credential",
    "include_in_menu": False,
    "label": "Username / Password",
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "inherit_from": [InfrahubKind.CREDENTIAL],
    "attributes": [
        {
            "name": "username",
            "kind": "Text",
            "optional": True,
            "branch": BranchSupportType.AGNOSTIC.value,
            "order_weight": 6000,
        },
        {
            "name": "password",
            "kind": "Password",
            "optional": True,
            "branch": BranchSupportType.AGNOSTIC.value,
            "order_weight": 7000,
        },
    ],
}

core_refresh_token = {
    "name": "RefreshToken",
    "namespace": "Internal",
    "description": "Refresh Token",
    "include_in_menu": False,
    "label": "Refresh Token",
    "display_labels": [],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {"name": "expiration", "kind": "DateTime", "optional": False},
    ],
    "relationships": [
        {
            "name": "account",
            "peer": InfrahubKind.GENERICACCOUNT,
            "optional": False,
            "cardinality": "one",
            "identifier": "account__refreshtoken",
        },
    ],
}

core_credential = {
    "name": "Credential",
    "namespace": "Core",
    "description": "A credential that could be referenced to access external services.",
    "include_in_menu": False,
    "label": "Credential",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["label__value"],
    "icon": "mdi:key-variant",
    "human_friendly_id": ["name__value"],
    "branch": BranchSupportType.AGNOSTIC.value,
    "uniqueness_constraints": [["name__value"]],
    "documentation": "/topics/auth",
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True, "order_weight": 1000},
        {"name": "label", "kind": "Text", "optional": True, "order_weight": 2000},
        {"name": "description", "kind": "Text", "optional": True, "order_weight": 3000},
    ],
}

core_generic_account = {
    "name": "GenericAccount",
    "namespace": "Core",
    "description": "User Account for Infrahub",
    "include_in_menu": False,
    "label": "Account",
    "icon": "mdi:account",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["label__value"],
    "human_friendly_id": ["name__value"],
    "branch": BranchSupportType.AGNOSTIC.value,
    "documentation": "/topics/auth",
    "uniqueness_constraints": [["name__value"]],
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True},
        {"name": "password", "kind": "HashedPassword", "unique": False},
        {"name": "label", "kind": "Text", "optional": True},
        {"name": "description", "kind": "Text", "optional": True},
        {
            "name": "account_type",
            "kind": "Text",
            "default_value": AccountType.USER.value,
            "enum": AccountType.available_types(),
        },
        {
            "name": "status",
            "kind": "Dropdown",
            "choices": [
                {
                    "name": AccountStatus.ACTIVE.value,
                    "label": "Active",
                    "description": "Account is allowed to login",
                    "color": "#52be80",
                },
                {
                    "name": AccountStatus.INACTIVE.value,
                    "label": "Inactive",
                    "description": "Account is not allowed to login",
                    "color": "#e74c3c",
                },
            ],
            "default_value": AccountStatus.ACTIVE.value,
        },
    ],
    "relationships": [{"name": "tokens", "peer": InfrahubKind.ACCOUNTTOKEN, "optional": True, "cardinality": "many"}],
}
