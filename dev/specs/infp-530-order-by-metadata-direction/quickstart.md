# Quickstart: Order by node metadata at the schema level

This walkthrough exercises the customer's primary use case (User Story 1) and validates the contract end-to-end across the three list paths.

## Scenario

A schema author defines `Documentation.Note` (called `DocumentationNote` informally) and attaches notes to a parent `Documentation.Article` via a many-cardinality relationship. The author wants every list view of `DocumentationNote` to default to newest-first, without callers passing an `order` argument.

## Schema

```yaml
nodes:
  - name: Article
    namespace: Documentation
    attributes:
      - { name: title, kind: Text }
    relationships:
      - { name: notes, peer: DocumentationNote, cardinality: many, kind: Component }

  - name: Note
    namespace: Documentation
    order_by:
      - node_metadata__created_at__desc
    attributes:
      - { name: body, kind: Text }
```

The `Note` schema has no user-defined timestamp; it relies on the node-level `created_at` metadata that Infrahub records automatically.

## Step 1 — Load the schema

```bash
infrahub schema load <path/to/schema.yml>
```

**Expected**: schema loads cleanly. The author has not used the reserved `node_metadata` name, and `created_at` is a supported metadata field.

**Negative check**: change the entry to `node_metadata__created_at__descending` and reload.

**Expected**: load fails with a message of the form:

```text
Documentation.Note: invalid direction (entry: 'node_metadata__created_at__descending'). Direction must be 'asc' or 'desc'.
```

Restore the correct entry before continuing.

## Step 2 — Create three notes

```bash
infrahub object create Documentation.Article --title "Onboarding"
infrahub object create Documentation.Note --body "first"  --notes_of <article-id>
sleep 1
infrahub object create Documentation.Note --body "second" --notes_of <article-id>
sleep 1
infrahub object create Documentation.Note --body "third"  --notes_of <article-id>
```

## Step 3 — Verify top-level list (Path 1)

```graphql
query {
  DocumentationNote {
    edges { node { body } }
  }
}
```

**Expected**: `third`, `second`, `first` in that order. UUID tiebreaker is appended but invisible here.

## Step 4 — Verify relationship-peer list (Path 2 — the customer's critical case)

```graphql
query {
  DocumentationArticle(ids: ["<article-id>"]) {
    edges {
      node {
        notes {
          edges { node { body } }
        }
      }
    }
  }
}
```

**Expected**: `third`, `second`, `first` — same order as the top-level path. Today this returns the notes in their default (UUID-fallback) order regardless of the schema author's intent; after the change, the peer schema's `order_by` is honored.

## Step 5 — Verify hierarchy list (Path 3)

Using a hierarchical schema (e.g., `LocationGeneric` with parent/child relationships) with `order_by: ["node_metadata__created_at__desc"]` on the hierarchical kind, fetch a parent's children:

```graphql
query {
  LocationGeneric(ids: ["<parent-id>"]) {
    edges {
      node {
        children {
          edges { node { name { value } } }
        }
      }
    }
  }
}
```

**Expected**: children appear in newest-first order, matching Paths 1 and 2.

## Step 6 — Verify default-ascending fallback

Reload the schema with `order_by: ["node_metadata__created_at"]` (no `__desc` suffix) and re-run Step 3.

**Expected**: `first`, `second`, `third`. The implicit-ascending default matches today's behavior for direction-less entries.

## Step 7 — Verify direction on a regular attribute

On any schema with a `name` text attribute, reload with `order_by: ["name__value__desc"]` and create items named `alpha`, `bravo`, `charlie`.

**Expected**: list returns `charlie`, `bravo`, `alpha`. Reloading with `order_by: ["name__value"]` returns `alpha`, `bravo`, `charlie`.

## Step 8 — Verify query-time precedence

Keep the `Documentation.Note` schema with `order_by: ["node_metadata__created_at__desc"]`. Run:

```graphql
query {
  DocumentationNote(order: { node_metadata: { created_at: ASC } }) {
    edges { node { body } }
  }
}
```

**Expected**: `first`, `second`, `third` — query-time argument fully replaces the schema-level default (no stacking).

## Step 9 — Verify reserved-name rejection

Attempt to load a schema that declares an attribute literally named `node_metadata`:

```yaml
nodes:
  - name: BadKind
    namespace: Test
    attributes:
      - { name: node_metadata, kind: Text }
```

**Expected**: schema load fails with:

```text
Test.BadKind: 'node_metadata' is a reserved name (attribute: 'node_metadata'). Rename this attribute or relationship.
```

## Success signal

When all nine steps pass on a fresh deployment, the feature is functionally complete from the schema-author and API-consumer perspective. Component-level cypher correctness is covered by the test plan generated in Phase 2.
