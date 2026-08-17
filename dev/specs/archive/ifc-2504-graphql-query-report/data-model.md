# Data Model: GraphQL Query Report Introspection

**Feature**: IFC-2504 | **Date**: 2026-04-25

## Overview

This feature introduces no new graph database entities. The `InfrahubGraphQLQueryReport` is a **transient response type** — computed on-the-fly from the submitted query string and discarded after the response. Nothing is persisted.

---

## Response Type: InfrahubGraphQLQueryReport

A structured analysis result for a submitted GraphQL query string.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `targets_unique_nodes` | Boolean | Yes | `true` if every operation in the query resolves to uniquely identifiable nodes; `false` otherwise. |

### Uniqueness Definition

`targets_unique_nodes` is `true` if and only if, for every top-level operation in the submitted query:

- The operation uses an `ids` argument **as a required argument**, OR
- The operation uses a field that matches the model's uniqueness constraints **as a required argument**

"Required argument" means the argument is either a non-nullable variable declared in the query, or a static literal value.

When `true`, Infrahub can limit artifact regeneration to only the nodes that changed. When `false`, all artifacts for the definition are regenerated on any relevant node change.

### Future Extension

The response type is designed to accommodate additional fields from `GraphQLQueryReport` without breaking existing callers:

- `requested_read` — which node kinds and fields the query reads
- `variables` — which variables the query declares
- `impacted_models` — which Infrahub models the query touches

These are already computed by `InfrahubGraphQLQueryAnalyzer.query_report`; this feature makes them accessible for future ad-hoc inspection.

---

## Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | String | Yes | Raw GraphQL query string to analyze. Must be syntactically valid GraphQL and reference types that exist in the current branch schema. |

### Error Conditions

| Condition | Behavior |
|-----------|----------|
| Empty string | GraphQL error returned |
| Syntactically invalid GraphQL | GraphQL error returned (raised during parse) |
| References non-existent node types | GraphQL error returned (caught by schema validation) |
