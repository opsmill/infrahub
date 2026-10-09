import json
from datetime import datetime, timezone

SCALAR_TYPES = [
    "STRING", "INTEGER", "FLOAT", "BOOLEAN",
    "DATE", "DATETIME", "LOCAL_DATETIME", "TIME", "LOCAL_TIME", "DURATION",
    "POINT",
]
VALID_TYPES = SCALAR_TYPES + ["LIST"] + [f"LIST<{t}>" for t in SCALAR_TYPES]


def prompt_type(prop_name):
    while True:
        t = input(f"      Type for '{prop_name}' {VALID_TYPES}: ").strip().upper()
        if t in VALID_TYPES:
            return t
        print(f"      Invalid type. Choose from: {VALID_TYPES}")


def define_properties():
    properties = {}
    print("    Properties (leave name blank to finish):")
    while True:
        name = input("      Property name: ").strip()
        if not name:
            break
        type_ = prompt_type(name)
        properties[name] = {
            "type": type_,
            "indexed": False,
            "unique": False,
            "existence": False,
        }
    return properties


def main():
    print("\nNeo4j Schema Definition Tool")
    print("Builds <db-name>-schema.json by defining your graph schema before the database exists.")
    print("=" * 60)

    schema = {"value": {}}
    node_labels = []

    print("\nStep 1: Define Node Labels")
    while True:
        label = input("  Node label (blank to finish): ").strip()
        if not label:
            break
        print(f"  Defining '{label}':")
        props = define_properties()
        schema["value"][label] = {
            "type": "node",
            "count": 0,
            "properties": props,
            "relationships": {},
            "labels": [],
        }
        node_labels.append(label)
        print(f"  '{label}' added.\n")

    if not node_labels:
        print("No nodes defined. Exiting.")
        return

    print(f"\nStep 2: Define Relationships")
    print(f"  Available nodes: {node_labels}")
    rel_types = set()

    while True:
        rel = input("\n  Relationship type (blank to finish): ").strip().upper()
        if not rel:
            break

        from_label = input(f"  From node: ").strip()
        to_label = input(f"  To node: ").strip()

        if from_label not in schema["value"]:
            print(f"  '{from_label}' not found. Skipping.")
            continue
        if to_label not in schema["value"]:
            print(f"  '{to_label}' not found. Skipping.")
            continue

        print(f"  Properties for [{rel}] (optional):")
        props = define_properties()

        schema["value"][from_label]["relationships"][rel] = {
            "direction": "out",
            "labels": [to_label],
            "count": 0,
            "properties": {k: {**v, "array": False} for k, v in props.items()},
        }

        schema["value"][to_label]["relationships"][rel] = {
            "direction": "in",
            "labels": [from_label],
            "count": 0,
            "properties": {k: {**v, "array": False} for k, v in props.items()},
        }

        schema["value"][rel] = {
            "type": "relationship",
            "count": 0,
            "properties": props,
        }

        rel_types.add(rel)
        print(f"  ({from_label})-[:{rel}]->({to_label}) added.")

    db_name = input("\nDatabase name for schema file (e.g. 'movies', 'supply-chain'): ").strip() or "neo4j"
    output_path = f"{db_name}-schema.json"
    schema["schema_retrieved_at"] = datetime.now(timezone.utc).isoformat()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    print(f"\nSchema saved to {output_path}")
    print(f"   Nodes:         {node_labels}")
    print(f"   Relationships: {sorted(rel_types)}")


if __name__ == "__main__":
    main()
