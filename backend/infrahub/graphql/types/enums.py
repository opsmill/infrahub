from graphene import Enum

from infrahub.core import constants
from infrahub.permissions import constants as permission_constants

CheckType = Enum.from_enum(constants.CheckType)

Severity = Enum.from_enum(constants.Severity)

BranchAwarePermissionDecision = Enum.from_enum(permission_constants.BranchAwarePermissionDecision)
