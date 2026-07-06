from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision

# Permission required to READ or WRITE the organisation-wide (global) preferences. Defined once here
# and shared by the preferences query and mutation resolvers so the gate stays consistent.
MANAGE_GLOBAL_PREFERENCES_PERMISSION = GlobalPermission(
    action=GlobalPermissions.MANAGE_GLOBAL_PREFERENCES.value,
    decision=PermissionDecision.ALLOW_ALL.value,
)
