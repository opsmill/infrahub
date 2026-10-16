# Contract: Masking of Spans and Logs

**Requirements**: FR-009 to FR-013a | **Clarifications**: 2026-10-14 (marker, always on)

## Where masking happens

| Output | Where | When |
|--------|-------|------|
| Span attributes | `infrahub.trace::MaskingSpanExporter`, wrapping the exporter of the tracer provider | On export, after every instrumentation has set its attributes |
| Span events, including exception events | Same exporter: the attributes of each event are masked with the same rules, and URL query strings inside `exception.message` and `exception.stacktrace` are replaced | On export |
| structlog log lines (API server, task worker) | `infrahub.log::mask_personal_data` processor | Before the renderer writes the line |
| Standard `logging` records (Prefect run loggers, gunicorn) | `infrahub.log::LogMaskingFilter` | Before any handler reads the record, including the handler that sends flow run logs to the Prefect API |

There is no setting to turn masking off.

## What is masked

The rules are in [data-model.md](../data-model.md), "Masking rule". They match on the attribute or
field key, at every level of nested mappings and lists. Text inside a free-text message is not
searched, with one exception: URL query strings are replaced in the message and the exception text of
every log line, and in `exception.message` of span events.

## Masked value

- A masked value is the string `[MASKED]`. The key stays.
- A URL keeps its path: `/api/oidc/provider/token?code=abc&state=xyz` becomes
  `/api/oidc/provider/token?[MASKED]`.
- A URL without a query string is unchanged.
- In `exception.message`, each URL keeps its path and its query string is replaced: `Client error for
  url 'https://idp.example.com/token?code=abc'` becomes `Client error for url
  'https://idp.example.com/token?[MASKED]'`. The rest of the message is unchanged. The same applies to
  the message and the exception text of a log line.
- The input mapping passed by the caller is not changed; masking returns a copy (the caller may still
  use it).

## Single sign-on

- The `sso_token_request` and account spans of `infrahub.api.oidc` and `infrahub.api.oauth2` no longer
  record the token response or the user information. They record `provider_name`, and the number of
  groups as `sso_group_count`.
- The log line "SSO user authenticated" has `account_id` and `groups`, not `user_name`.

## Kept readable

Cypher text, URL paths, GraphQL operation names and query names (`query_name`).
