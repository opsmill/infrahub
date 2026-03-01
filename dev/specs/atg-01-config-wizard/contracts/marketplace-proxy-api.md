# API Contract: Marketplace Proxy Endpoints

**Feature**: atg-01-config-wizard | **Date**: 2026-02-26

## Overview

Backend REST endpoints that proxy requests to the Infrahub Marketplace GraphQL API at `https://marketplace.infrahub.app/graphql`. These endpoints normalize responses, handle errors, and leverage the existing `HttpxAdapter` for HTTP communication.

## Endpoints

### GET /api/marketplace/schemas

Fetch the catalog of available schemas from the marketplace.

**Request**:
- Method: `GET`
- Authentication: Required (standard Infrahub auth)
- Query Parameters:
  - `search` (optional, string): Filter schemas by name/displayName
  - `tags` (optional, string, comma-separated): Filter schemas by tag names

**Response** (200):
```json
{
  "schemas": [
    {
      "id": "ab2fd4c6-3304-4ec8-b205-1a636dcc81b0",
      "name": "vlan-translation",
      "namespace": "infrahub",
      "display_name": "VLAN Translation",
      "description": "VLAN translation — QinQ and VLAN ID mapping between domains.",
      "download_count": 1,
      "upvote_count": 1,
      "fork_count": 0,
      "visibility": "public",
      "tags": [
        { "id": "f6848e80-...", "name": "experimental" }
      ],
      "versions": [
        { "id": "v1-uuid", "semver": "1.0.0", "status": "published", "download_count": 5 }
      ]
    }
  ],
  "total_count": 50
}
```

**Response** (502):
```json
{
  "detail": "Unable to reach the Infrahub Marketplace. Please try again later."
}
```

---

### GET /api/marketplace/collections

Fetch the catalog of available collections from the marketplace.

**Request**:
- Method: `GET`
- Authentication: Required

**Response** (200):
```json
{
  "collections": [
    {
      "id": "2220e4a5-a394-45f1-a5ed-42a247e15f20",
      "name": "base",
      "display_name": "Base Schema",
      "description": "This collection contains some base schemas to get started with.",
      "schema_count": 5,
      "download_count": 10,
      "upvote_count": 3,
      "items": [
        { "id": "schema-uuid", "name": "base-device", "display_name": "Base Device" }
      ]
    }
  ],
  "total_count": 1
}
```

---

### GET /api/marketplace/tags

Fetch available tags for filtering.

**Request**:
- Method: `GET`
- Authentication: Required

**Response** (200):
```json
{
  "tags": [
    { "id": "f6848e80-...", "name": "experimental", "count": 15 },
    { "id": "a1b2c3d4-...", "name": "networking", "count": 8 }
  ]
}
```

---

### GET /api/marketplace/schemas/{schema_id}/versions/{version_id}

Fetch the full content of a specific schema version for installation.

**Request**:
- Method: `GET`
- Authentication: Required
- Path Parameters:
  - `schema_id` (string, required): Marketplace schema UUID
  - `version_id` (string, required): Marketplace version UUID

**Response** (200):
```json
{
  "id": "version-uuid",
  "semver": "1.0.0",
  "content": "---\nversion: '1.0'\nnodes:\n  - name: VLANTranslation\n    namespace: Infra\n    ...",
  "download_url": "https://marketplace.infrahub.app/download/...",
  "dependencies": [
    { "id": "dep-uuid", "name": "base-device", "namespace": "infrahub" }
  ]
}
```

**Response** (404):
```json
{
  "detail": "Schema version not found in the marketplace."
}
```

---

### POST /api/marketplace/install

Trigger installation of selected marketplace schemas into a repository.

**Request**:
- Method: `POST`
- Authentication: Required (admin or write permissions)
- Body:
```json
{
  "repository_id": "repo-uuid",
  "schema_version_ids": ["version-uuid-1", "version-uuid-2"],
  "branch_name": "main"
}
```

**Response** (202):
```json
{
  "task_id": "prefect-flow-run-id",
  "message": "Schema installation started. Check task status for progress."
}
```

**Response** (400):
```json
{
  "detail": "No schema version IDs provided."
}
```

**Response** (404):
```json
{
  "detail": "Repository not found."
}
```

## Error Handling

All endpoints follow the same error pattern:

| Status | Meaning | When |
|--------|---------|------|
| 200 | Success | Normal response |
| 202 | Accepted | Async job submitted (install endpoint) |
| 400 | Bad Request | Invalid input parameters |
| 401 | Unauthorized | Missing or invalid auth token |
| 404 | Not Found | Referenced entity doesn't exist |
| 502 | Bad Gateway | Marketplace API unreachable or returned error |

## Notes

- All responses use `snake_case` field naming (Infrahub backend convention), regardless of the marketplace API's `camelCase` responses.
- The proxy layer handles field name transformation from marketplace `camelCase` to Infrahub `snake_case`.
- Rate limiting and caching may be added as future enhancements; the initial implementation proxies requests directly.
