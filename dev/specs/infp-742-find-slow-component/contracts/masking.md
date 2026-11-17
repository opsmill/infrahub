# Contract: Masking of Spans

**Requirements**: FR-009 to FR-013a | **Clarifications**: 2026-10-14 (marker, always on), 2026-10-19 (no log masking, request span hook)

## Where masking happens

| Output | Where | When |
|--------|-------|------|
| Request span attributes (URL, client IP address) | The request hook passed to the FastAPI instrumentation in `infrahub.server` | When the request span starts, after the instrumentation has set them |
| Span attributes | `infrahub.trace::MaskingSpanExporter`, wrapping the exporter of the tracer provider | On export, after every instrumentation has set its attributes |
| Span events, including exception events | Same exporter: the attributes of each event are masked with the same rules, and URL query strings inside `exception.message` and `exception.stacktrace` are replaced | On export |

There is no setting to turn masking off. Log lines are not masked: a leak in a log line is fixed where
the line is written (FR-013).

## What is masked

The rules are in [data-model.md](../data-model.md), "Masking rule". They match on the attribute key,
at every level of nested mappings and lists. Text inside a free-text value is not searched, with one
exception: URL query strings are replaced in `exception.message` and `exception.stacktrace` of span
events.

## Masked value

- A masked value is the string `[MASKED]`. The key stays.
- A URL keeps its scheme, hostname and path: `https://host/api/oidc/provider/token?code=abc&state=xyz`
  becomes `https://host/api/oidc/provider/token?[MASKED]`.
- A URL without a query string is unchanged.
- In `exception.message`, each URL keeps its path and its query string is replaced: `Client error for
  url 'https://idp.example.com/token?code=abc'` becomes `Client error for url
  'https://idp.example.com/token?[MASKED]'`. The rest of the message is unchanged.
- The input mapping passed by the caller is not changed; masking returns a copy (the caller may still
  use it).

## Single sign-on

- The `sso_token_request` and account spans of `infrahub.api.oidc` and `infrahub.api.oauth2` no longer
  record the token response or the user information. They record `provider_name`, and the number of
  groups as `sso_group_count`.
- The log line "SSO user authenticated" has `account_id` and `groups`, not `user_name`.

## Kept readable

Cypher text, URL paths, GraphQL operation names and query names (`query_name`).
