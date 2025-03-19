from enum import Enum

TELEMETRY_KIND: str = "community"
TELEMETRY_VERSION: str = "20250318"


class InfrahubType(str, Enum):
    COMMUNITY = "community"
    ENTERPRISE = "enterprise"
