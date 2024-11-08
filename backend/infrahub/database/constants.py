from enum import Enum


class DatabaseType(str, Enum):
    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"


class Neo4jRuntime(str, Enum):
    DEFAULT = "default"
    INTERPRETED = "interpreted"
    SLOTTED = "slotted"
    PIPELINED = "pipelined"
    PARALLEL = "parallel"
    UNDEFINED = "undefined"


class IndexType(str, Enum):
    TEXT = "text"
    RANGE = "range"
    LOOKUP = "lookup"
    NOT_APPLICABLE = "not_applicable"


class EntityType(str, Enum):
    NODE = "node"
    RELATIONSHIP = "relationship"
