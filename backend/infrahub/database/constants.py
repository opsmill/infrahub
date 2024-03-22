from enum import Enum


class DatabaseType(str, Enum):
    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"


class Neo4jRuntime(str, Enum):
    DEFAULT = "default"
    INTERPRETED = "interpreted"
    SLOTTED = "slotted"
    PIPELINED = "pipelined"
