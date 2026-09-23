# Schema Guardrail Reference

## Schema File

`<db-name>-schema.json` — name after your database (e.g. `movies-schema.json`). Place anywhere in the project.

### Generate from existing database (requires APOC)
```bash
pip install neo4j python-dotenv
python scripts/generate_schema.py <db-name>
```
`.env` (add to `.gitignore`):
```
NEO4J_URI=neo4j+s://<instance>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

### Build interactively (no DB needed)
```bash
python scripts/define_schema.py
```

### Convert from existing JSON schema
```bash
python scripts/import_neo4j_schema.py path/to/input-schema.json
```
Auto-detects: `neo4j-graphrag-python` SchemaBuilder, `graph-schema-introspector`, `graph-schema-json-js-utils`, `mcp-neo4j-data-modeling`.

---

## Schema Format (APOC meta.schema)

```json
{
  "schema_retrieved_at": "2026-06-06T10:00:00+00:00",
  "value": {
    "Theme": {
      "type": "node",
      "properties": {
        "name":     { "type": "STRING" },
        "theme_id": { "type": "INTEGER" }
      },
      "relationships": {
        "HAS_SET": { "direction": "out", "labels": ["Set"], "properties": {} }
      }
    },
    "Set": {
      "type": "node",
      "properties": {
        "name":         { "type": "STRING" },
        "id":           { "type": "STRING" },
        "year":         { "type": "INTEGER" },
        "pieces":       { "type": "INTEGER" }
      },
      "relationships": {
        "HAS_SET":     { "direction": "in",  "labels": ["Theme"], "properties": {} },
        "HAS_MINIFIG": { "direction": "out", "labels": ["Minifig"],
                         "properties": { "quantity": { "type": "INTEGER" } } }
      }
    },
    "Minifig": {
      "type": "node",
      "properties": {
        "name":      { "type": "STRING" },
        "fig_num":   { "type": "STRING" },
        "num_parts": { "type": "INTEGER" }
      }
    },
    "HAS_MINIFIG": {
      "type": "relationship",
      "properties": { "quantity": { "type": "INTEGER" } }
    }
  }
}
```

---

## Validation Rules

Reason about intent before asking. Ask only when unable to resolve — never generate wrong Cypher silently, but don't stop when a safe interpretation exists.

**1. Existence** — labels, rel-types, properties must be in schema. On miss: try synonym resolution → structural match → ask.

**2. Synonym mapping**
- Unambiguous → resolve silently: `ℹ️ Resolved 'Minifigure' → 'Minifig'.`
- Ambiguous → pick most likely from context, note: `ℹ️ 'Fig' → 'Minifig' (context). Correct if wrong.`
- No match → surface candidates: `⚠️ 'Character' not found. Did you mean: Theme, Set, Minifig?`

**3. Property type** — valid types: `STRING` `INTEGER` `FLOAT` `BOOLEAN` `DATE` `DATETIME` `LOCAL_DATETIME` `TIME` `LOCAL_TIME` `DURATION` `POINT` `LIST<TYPE>`. On mismatch:
- String against INTEGER (`'unknown'`, `'n/a'`) → rewrite as `IS NULL` and note
- Clearly wrong literal → propose correction and ask

**4. Relationship direction** — `out` = `(a)-[:R]->(b)`, `in` = `(b)-[:R]->(a)`. Wrong direction → correct silently, note:
```
HAS_SET | Schema: Theme──→Set | Prompt: Set──→Theme | ↩ Corrected
```

**5. Generate** — Cypher 25; use literals for interactive execution, `$param` for code generation; return only schema-declared properties.

---

## Examples

### Valid query
```
User: "List minifigures in the Cloud City set"

✅ Set | ✅ Minifig | ✅ HAS_MINIFIG (Set→Minifig)

CYPHER 25
MATCH (s:Set {id: $setId})-[:HAS_MINIFIG]->(m:Minifig)
RETURN m.name AS minifigName, m.fig_num AS figNum, m.num_parts AS numParts
ORDER BY m.name
// Parameters: { setId: "10123-1" }
```

### Entity not found
```
User: "Find all Character nodes linked to a Movie"

❌ Character NOT FOUND | ❌ Movie NOT FOUND
Schema nodes: Theme, Set, Minifig

⚠️ Neither 'Character' nor 'Movie' exists in this schema.
Did you mean Set linked to Minifig, or are you querying a different database?
```

### Synonym resolved
```
User: "Find all Minifigures in a set"

ℹ️ Resolved 'Minifigure' → 'Minifig'. Proceeding.

CYPHER 25
MATCH (s:Set {id: $setId})-[:HAS_MINIFIG]->(m:Minifig)
RETURN m.name AS minifigName, m.fig_num AS figNum
// Parameters: { setId: $setId }
```

### Type mismatch
```
User: "Find sets where pieces is 'unknown'"

Set.pieces declared INTEGER, value 'unknown' is a STRING.
Interpreting as null/missing-value check.

ℹ️ Rewritten: WHERE s.pieces IS NULL. Correct if you meant something else.

CYPHER 25
MATCH (s:Set) WHERE s.pieces IS NULL RETURN s.name, s.id
```

---

## Commit or ignore schema.json file?

**Commit** when schema is stable and shared, or needed for CI without a live DB.
**Ignore** (`*-schema.json` → `.gitignore`) when schema contains sensitive names or evolves rapidly.

`schema_retrieved_at` in the file records when the snapshot was taken.
