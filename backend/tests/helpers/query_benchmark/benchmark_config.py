from dataclasses import dataclass

from infrahub.database import Neo4jRuntime
from tests.helpers.constants import NEO4J_ENTERPRISE_IMAGE


@dataclass
class BenchmarkConfig:
    neo4j_image: str = NEO4J_ENTERPRISE_IMAGE
    neo4j_runtime: Neo4jRuntime = Neo4jRuntime.DEFAULT
    load_db_indexes: bool = False

    def __str__(self) -> str:
        return f"{self.neo4j_image=} ; runtime: {self.neo4j_runtime} ; indexes: {self.load_db_indexes}"
