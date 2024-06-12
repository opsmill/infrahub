from neo4j.graph import Path


class InvalidCypherPathError(Exception):
    def __init__(self, cypher_path: Path) -> None:
        self.cypher_path = cypher_path

    def __str__(self) -> str:
        path_repr = ""
        for relationship in self.cypher_path.relationships:
            path_repr += f"(type={relationship.type} {relationship.start_node}-{relationship.end_node})"
        return f"Cannot parse cypher path {path_repr}"
