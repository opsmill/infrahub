from graphene import Enum

from infrahub.core.constants import Severity as PySeverity

Severity = Enum.from_enum(PySeverity)
