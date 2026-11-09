# Extraction Record

**Extracted on**: 2026-07-31
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- None. This spec has no `research.md`, so no decision records were extracted.

## Knowledge Updated

- None. The feature is already documented in `dev/knowledge/backend/webhooks.md`: the `WebhookHeader`
  model, static and environment-variable resolution, the `CoreKeyValue` schema and `headers`
  relationship, cache invalidation via `TRIGGER_KEYVALUE_WEBHOOK_INVALIDATE`, and the
  KeyValue-to-webhook query. The doc reflects the implemented behavior, which supersedes this early
  draft on one point: a missing environment variable fails the delivery with a `CONFIG` error rather
  than being skipped.

## Guidelines Updated

- None.

## Archive

Spec directory moved to `specs/archive/infp-445-webhook-headers/` as a historical record.
