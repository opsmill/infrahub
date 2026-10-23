from enum import StrEnum


class DatabaseType(StrEnum):
    NEO4J = "neo4j"


class Neo4jRuntime(StrEnum):
    DEFAULT = "default"
    INTERPRETED = "interpreted"
    SLOTTED = "slotted"
    PIPELINED = "pipelined"
    PARALLEL = "parallel"
    UNDEFINED = "undefined"


class IndexType(StrEnum):
    TEXT = "text"
    RANGE = "range"
    LOOKUP = "lookup"


class EntityType(StrEnum):
    NODE = "node"
    RELATIONSHIP = "relationship"
