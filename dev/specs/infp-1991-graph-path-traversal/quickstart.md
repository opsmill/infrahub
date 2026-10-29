# Quickstart: Graph Path Traversal

## Prerequisites

- Infrahub development environment running (`uv sync --all-groups`, `cd frontend/app && npm install`)
- Neo4j database running with sample data
- Familiarity with the Infrahub query class pattern (`backend/infrahub/core/query/`)

## Backend: Add the Path Traversal Query

### 1. Create the Cypher query class

New file: `backend/infrahub/core/query/path.py`

Follow the `Query` base class pattern from `backend/infrahub/core/query/__init__.py`. Key references:
- `NodeGetHierarchyQuery` in `query/node.py` for variable-length path matching
- `Branch.get_query_filter_path()` for branch-aware filtering
- `db.render_list_comprehension()` for Neo4j/Memgraph portability

### 2. Create the GraphQL query

New file: `backend/infrahub/graphql/queries/path.py`

Follow the pattern of `queries/search.py`:
- Define `ObjectType` classes for response structure
- Define `InputObjectType` for request parameters
- Write an async resolver that uses the query class from step 1
- Export a `Field()` with arguments and resolver

### 3. Register in the schema

- Export from `backend/infrahub/graphql/queries/__init__.py`
- Add to `InfrahubBaseQuery` in `backend/infrahub/graphql/schema.py`

### 4. Test

```bash
uv run invoke backend.test-unit  # Unit tests for query building
```

## Frontend: Add the Path Visualization

### 1. Install dependencies

```bash
cd frontend/app && npm install @xyflow/react dagre @types/dagre
```

### 2. Create the domain layer

New directory: `frontend/app/src/entities/path-traversal/`

Structure:
```
path-traversal/
├── domain/
│   ├── path-traversal.query-keys.ts
│   ├── path-traversal.query.ts
│   └── get-path-traversal.ts
└── ui/
    ├── path-traversal-page.tsx
    ├── path-flow-graph.tsx       # React Flow canvas with dagre layout
    ├── infra-node.tsx            # Custom node component (kind icon + label)
    ├── path-edge.tsx             # Custom edge component (highlighted vs dimmed)
    └── node-selector.tsx
```

### 3. Build the GraphQL query

Use `json-to-graphql-query` following the pattern in `entities/nodes/object/domain/get-objects.ts`.

### 4. Build the visualization

Use `@xyflow/react` with `dagre` for automatic hierarchical layout. Convert path results to React Flow nodes/edges, compute positions with dagre, and render with custom node/edge components. Reference the tree component in `entities/nodes/hierarchy/ui/` for interactive patterns.

### 4. Test

```bash
cd frontend/app && npm run test  # Unit tests
```

## Verification

```graphql
query {
  InfrahubPathTraversal(data: {
    sourceId: "<uuid-of-node-A>"
    destinationId: "<uuid-of-node-B>"
  }) {
    paths {
      nodes { id kind displayLabel }
      relationships { id name direction }
      depth
    }
    totalPathsFound
  }
}
```
