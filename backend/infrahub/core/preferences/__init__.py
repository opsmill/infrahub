from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision

from .models import (
    GLOBAL_PREFERENCE_LOCK_NAME,
    GLOBAL_PREFERENCE_LOCK_NAMESPACE,
    GlobalPreference,
    UserPreference,
)

# Permission required to manage the org-wide GlobalPreference singleton. Defined once here and
# shared by both the preferences query and mutation modules to keep the gate consistent.
MANAGE_GLOBAL_PREFERENCES_PERMISSION = GlobalPermission(
    action=GlobalPermissions.MANAGE_GLOBAL_PREFERENCES.value,
    decision=PermissionDecision.ALLOW_ALL.value,
)

__all__ = [
    "GLOBAL_PREFERENCE_LOCK_NAME",
    "GLOBAL_PREFERENCE_LOCK_NAMESPACE",
    "MANAGE_GLOBAL_PREFERENCES_PERMISSION",
    "GlobalPreference",
    "UserPreference",
]
