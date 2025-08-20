from graphene import Enum

from infrahub.core import constants
from infrahub.permissions import constants as permission_constants

CheckType = Enum.from_enum(constants.CheckType)

DiffAction = Enum.from_enum(constants.DiffAction)

Severity = Enum.from_enum(constants.Severity)

BranchRelativePermissionDecision = Enum.from_enum(permission_constants.BranchRelativePermissionDecision)
