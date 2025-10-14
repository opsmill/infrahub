from enum import StrEnum


class DatabaseType(StrEnum):
    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"


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
    NOT_APPLICABLE = "not_applicable"


class EntityType(StrEnum):
    NODE = "node"
    RELATIONSHIP = "relationship"
