from enum import Enum


class GeneratorDefinitionRunSource(Enum):
    PROPOSED_CHANGE = "proposed_change"
    MERGE = "merge"
    UNKNOWN = "unknown"
