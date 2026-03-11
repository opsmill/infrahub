# Quickstart: Custom HTTP Headers for Webhooks

**Feature**: INFP-445 | **Date**: 2026-03-11

## Prerequisites

- Infrahub instance running with this feature branch
- At least one webhook (Standard or Custom) configured

## 1. Create a Key-Value Pair (Static Header)

```graphql
mutation {
  CoreKeyValueStaticCreate(data: {
    name: { value: "source-system-header" }
    key: { value: "X-Source-System" }
    value: { value: "infrahub" }
  }) {
    ok
    object { id }
  }
}
```

## 2. Create a Key-Value Pair (Sensitive/Password Header)

```graphql
mutation {
  CoreKeyValuePasswordCreate(data: {
    name: { value: "ansible-auth-token" }
    key: { value: "Authorization" }
    value: { value: "Bearer eyJhbGciOiJIUzI1NiIs..." }
  }) {
    ok
    object { id }
  }
}
```

The value is masked as `***` when queried back.

## 3. Create a Key-Value Pair (Environment Variable Header)

```graphql
mutation {
  CoreKeyValueEnvironmentVariableCreate(data: {
    name: { value: "vault-api-key" }
    key: { value: "X-API-Key" }
    value: { value: "VAULT_API_KEY" }
  }) {
    ok
    object { id }
  }
}
```

The environment variable `VAULT_API_KEY` is resolved on the Prefect worker at send time.

## 4. Link Headers to a Webhook

```graphql
mutation {
  CoreStandardWebhookUpdate(data: {
    id: "<webhook-id>"
    headers: [
      { id: "<source-system-header-id>" }
      { id: "<ansible-auth-token-id>" }
      { id: "<vault-api-key-id>" }
    ]
  }) {
    ok
    object {
      id
      headers { edges { node { name { value } key { value } } } }
    }
  }
}
```

## 5. Verify Headers in Webhook Requests

When the webhook fires, the HTTP request includes:

```http
POST /webhook-endpoint HTTP/1.1
Content-Type: application/json
Accept: application/json
X-Source-System: infrahub
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
X-API-Key: <resolved-from-VAULT_API_KEY-env-var>
webhook-id: msg_...
webhook-timestamp: ...
webhook-signature: v1,...
```

Custom headers merge with system defaults. If a custom header name conflicts with a system header (e.g., `Content-Type`), the custom value takes precedence.

## 6. Reuse Across Webhooks

The same key-value pair can be linked to multiple webhooks:

```graphql
mutation {
  CoreCustomWebhookUpdate(data: {
    id: "<another-webhook-id>"
    headers: [{ id: "<ansible-auth-token-id>" }]
  }) {
    ok
  }
}
```

Update the key-value pair value once → all linked webhooks use the new value on their next trigger.

## Edge Cases

- **Missing environment variable**: Header is skipped; remaining headers are sent; warning logged with the missing variable name
- **Duplicate header names**: Last-associated value wins; system logs a warning
- **Deleted key-value pair**: Relationship automatically cleaned up; webhook continues without that header
