# Extraction Record

**Extracted on**: 2026-08-14
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0020-analyzer-single-source-of-truth-for-query-targeting.md` (from RES-001)

## Knowledge Updated

- `dev/knowledge/backend/query-target-uniqueness.md` (new file - pinning rules, impact scopes, how to inspect a query)

## Guidelines Updated

- `dev/guidelines/backend/graphql.md` (new file - root-level query fields, resolver conventions, invalid user input, testing)

## User-Facing Documentation Updated

- `docs/docs/artifacts/overview.mdx` (When artifacts regenerate - new "Targeted regeneration and your query" section)
- `python_sdk/infrahub_sdk/ctl/graphql.py` and the regenerated `python_sdk/docs/docs/infrahubctl/infrahubctl-graphql.mdx` (`query-report` help text). Separate repository - needs its own commit and PR.

## Notes

The uniqueness rules described in `research.md` (RES-001) and `data-model.md` are the original,
narrower semantics. They were broadened after this spec shipped to cover `hfid`, cardinality-one
relationships, and composite uniqueness constraints. The extracted documentation describes the
current behavior, not the spec text.

## Archive

Spec directory moved to `dev/specs/archive/ifc-2504-graphql-query-report/` as a historical record.
