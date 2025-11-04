from enum import StrEnum

TELEMETRY_KIND: str = "community"
TELEMETRY_VERSION: str = "20250318"


class InfrahubType(StrEnum):
    COMMUNITY = "community"
    ENTERPRISE = "enterprise"
