"""
Export APOC meta.schema from a live Neo4j instance.

Usage:
    python scripts/generate_schema.py [db-name]

Reads credentials from environment variables or a .env file:
    NEO4J_URI       (default: bolt://localhost:7687)
    NEO4J_USERNAME  (default: neo4j)
    NEO4J_PASSWORD  (required)
    NEO4J_DATABASE  (default: db-name arg or "neo4j")

Output: <db-name>-schema.json in the current directory.
Add *-schema.json to .gitignore if the schema contains sensitive structure.
"""

import os
import json
import sys
from datetime import datetime, timezone

from neo4j import GraphDatabase

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional; env vars already set take precedence

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")


def fetch_and_map_schema(db_name=None):
    if not PASSWORD:
        print("Error: NEO4J_PASSWORD is not set. Add it to your .env file or environment.")
        sys.exit(1)

    name = db_name or os.getenv("NEO4J_DATABASE", "neo4j")
    print(f"Connecting to {URI} (database: {name}) ...")

    try:
        with GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD)) as driver:
            records, _, _ = driver.execute_query(
                "CALL apoc.meta.schema()", database_=name
            )

            if not records:
                print("No schema records returned. Is APOC installed?")
                return

            raw_schema = records[0].data()
            raw_schema["schema_retrieved_at"] = datetime.now(timezone.utc).isoformat()

            output_path = f"{name}-schema.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(raw_schema, f, indent=2)

            print(f"Schema saved to {output_path}")

    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    db_name = sys.argv[1] if len(sys.argv) > 1 else None
    fetch_and_map_schema(db_name)
