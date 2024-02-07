from graphene import Enum

from infrahub.core import constants

CheckType = Enum.from_enum(constants.CheckType)

Severity = Enum.from_enum(constants.Severity)
