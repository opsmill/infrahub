"""
Converts Neo4j schema JSON formats into an APOC meta.schema-compatible `*-schema.json` file.

Supported formats (auto-detected):
  - neo4j-graphrag-python SchemaBuilder JSON
  - Neo4j standard graph schema JSON (graph-schema-introspector, graph-schema-json-js-utils,
    mcp-neo4j-data-modeling)

Usage:
    python scripts/import_neo4j_schema.py <path-to-schema.json>
"""

import json
import os
import sys
from datetime import datetime, timezone


def neo4j_type_to_apoc(type_def):
    if not isinstance(type_def, dict):
        return "STRING"
    mapping = {
        "string": "STRING",
        "integer": "INTEGER",
        "float": "FLOAT",
        "boolean": "BOOLEAN",
        "date": "DATE",
        "datetime": "DATETIME",
        "local_datetime": "LOCAL_DATETIME",
        "time": "TIME",
        "local_time": "LOCAL_TIME",
        "duration": "DURATION",
        "point": "POINT",
        "array": "LIST",
        "list": "LIST",
    }
    return mapping.get(type_def.get("type", "string").lower(), "STRING")


def convert_graphrag(schema):
    """Convert neo4j-graphrag-python SchemaBuilder format to APOC format."""
    data = schema.get("schema", schema)
    apoc = {"value": {}}

    # Parse node types — can be strings or dicts
    node_labels = []
    for nt in data.get("node_types", []):
        if isinstance(nt, str):
            label = nt
            properties = {"name": {"type": "STRING", "indexed": False, "unique": False, "existence": False}}
        else:
            label = nt.get("label", nt.get("name", "Unknown"))
            properties = {}
            for prop in nt.get("properties", []):
                if isinstance(prop, str):
                    properties[prop] = {"type": "STRING", "indexed": False, "unique": False, "existence": False}
                else:
                    properties[prop.get("name", prop.get("token", "prop"))] = {
                        "type": prop.get("type", "STRING").upper(),
                        "indexed": False,
                        "unique": False,
                        "existence": False,
                    }
            if not properties:
                properties["name"] = {"type": "STRING", "indexed": False, "unique": False, "existence": False}

        apoc["value"][label] = {
            "type": "node",
            "count": 0,
            "properties": properties,
            "relationships": {},
            "labels": [],
        }
        node_labels.append(label)

    # Parse relationship types — can be strings or dicts
    rel_labels = []
    for rt in data.get("relationship_types", []):
        label = rt if isinstance(rt, str) else rt.get("label", rt.get("name", "RELATED"))
        rel_labels.append(label)
        apoc["value"][label] = {"type": "relationship", "count": 0, "properties": {}}

    # Wire up directions from patterns: [source, rel, target]
    for pattern in data.get("patterns", []):
        if len(pattern) != 3:
            continue
        from_label, rel_token, to_label = pattern

        if from_label in apoc["value"]:
            apoc["value"][from_label]["relationships"][rel_token] = {
                "direction": "out",
                "labels": [to_label],
                "count": 0,
                "properties": {},
            }

        if to_label in apoc["value"]:
            apoc["value"][to_label]["relationships"][rel_token] = {
                "direction": "in",
                "labels": [from_label],
                "count": 0,
                "properties": {},
            }

    return apoc


def resolve_ref(ref, node_labels, node_obj_types):
    key = ref.lstrip("#")
    if key in node_labels:
        return node_labels[key]
    if key in node_obj_types:
        obj = node_obj_types[key]
        label_ref = obj.get("labels", [{}])[0].get("$ref", "").lstrip("#")
        return node_labels.get(label_ref, key)
    return key


def convert_standard(neo4j_schema):
    """Convert Neo4j standard graph schema JSON format to APOC format."""
    graph = neo4j_schema.get("graphSchemaRepresentation", {}).get("graphSchema", {})

    node_labels = {nl["$id"]: nl["token"] for nl in graph.get("nodeLabels", [])}
    rel_types = {rt["$id"]: rt["token"] for rt in graph.get("relationshipTypes", [])}
    node_obj_types = {n["$id"]: n for n in graph.get("nodeObjectTypes", [])}
    rel_obj_types = graph.get("relationshipObjectTypes", [])

    apoc = {"value": {}}

    for nid, nobj in node_obj_types.items():
        label_ref = nobj.get("labels", [{}])[0].get("$ref", "").lstrip("#")
        label = node_labels.get(label_ref, nid)
        properties = {}
        for prop in nobj.get("properties", []):
            properties[prop["token"]] = {
                "type": neo4j_type_to_apoc(prop.get("type", {})),
                "indexed": False,
                "unique": False,
                "existence": not prop.get("nullable", True),
            }
        apoc["value"][label] = {
            "type": "node",
            "count": 0,
            "properties": properties,
            "relationships": {},
            "labels": [],
        }

    for robj in rel_obj_types:
        rel_token = rel_types.get(robj["type"]["$ref"].lstrip("#"), "UNKNOWN")
        from_label = resolve_ref(robj["from"]["$ref"], node_labels, node_obj_types)
        to_label = resolve_ref(robj["to"]["$ref"], node_labels, node_obj_types)

        rel_props = {}
        for prop in robj.get("properties", []):
            rel_props[prop["token"]] = {
                "type": neo4j_type_to_apoc(prop.get("type", {})),
                "indexed": False,
                "unique": False,
                "existence": not prop.get("nullable", True),
                "array": False,
            }

        if from_label in apoc["value"]:
            apoc["value"][from_label]["relationships"][rel_token] = {
                "direction": "out", "labels": [to_label], "count": 0, "properties": rel_props,
            }

        if to_label in apoc["value"]:
            apoc["value"][to_label]["relationships"][rel_token] = {
                "direction": "in", "labels": [from_label], "count": 0, "properties": rel_props,
            }

        apoc["value"][rel_token] = {
            "type": "relationship",
            "count": 0,
            "properties": {k: {kk: vv for kk, vv in v.items() if kk != "array"} for k, v in rel_props.items()},
        }

    return apoc


def detect_and_convert(schema):
    """Auto-detect schema format and convert to APOC."""
    # graphrag format: has 'schema' key with 'node_types' and 'patterns'
    data = schema.get("schema", schema)
    if "node_types" in data and "patterns" in data:
        print("Detected: neo4j-graphrag-python SchemaBuilder format")
        return convert_graphrag(schema)

    # Neo4j standard JSON format
    if "graphSchemaRepresentation" in schema:
        print("Detected: Neo4j standard graph schema JSON format")
        return convert_standard(schema)

    raise ValueError(
        "Unrecognised schema format. Supported: neo4j-graphrag-python SchemaBuilder, "
        "Neo4j standard graph schema JSON (graphSchemaRepresentation)."
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_neo4j_schema.py <path-to-schema.json>")
        print("Supported formats: neo4j-graphrag-python SchemaBuilder, Neo4j standard graph schema JSON")
        sys.exit(1)

    input_path = sys.argv[1]
    with open(input_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    apoc = detect_and_convert(schema)
    apoc["schema_retrieved_at"] = datetime.now(timezone.utc).isoformat()

    base = os.path.splitext(os.path.basename(input_path))[0]
    output_path = f"{base}.json" if base.endswith("-schema") else f"{base}-schema.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(apoc, f, indent=2)

    node_count = sum(1 for v in apoc["value"].values() if v.get("type") == "node")
    rel_count = sum(1 for v in apoc["value"].values() if v.get("type") == "relationship")
    print(f"✅ Converted: {node_count} node types, {rel_count} relationship types")
    print(f"   Saved to {output_path}")


if __name__ == "__main__":
    main()
