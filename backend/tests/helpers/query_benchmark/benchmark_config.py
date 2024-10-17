from dataclasses import dataclass

from infrahub.core.schema import SchemaRoot
from infrahub.database import Neo4jRuntime
from tests.helpers.constants import NEO4J_ENTERPRISE_IMAGE
from tests.helpers.query_benchmark.data_generator import DataGenerator


@dataclass
class BenchmarkConfig:
    # data_generator: DataGenerator
    # schema_root: SchemaRoot
    neo4j_image: str = NEO4J_ENTERPRISE_IMAGE
    neo4j_runtime: Neo4jRuntime = Neo4jRuntime.DEFAULT
    load_db_indexes: bool = False

    def __str__(self) -> str:
        return f"{self.neo4j_image=} ; runtime: {self.neo4j_runtime} ; indexes: {self.load_db_indexes}"
