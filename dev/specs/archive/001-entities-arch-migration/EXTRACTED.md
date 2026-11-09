# Extraction Record

**Extracted on**: 2026-07-03
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- dev/adr/0006-frontend-entity-layers.md (from research.md D1–D5 + tasks.md decision log 3)

The remaining reconciled decisions (generated types permitted in `domain/`, review-only
enforcement) are recorded in `dev/knowledge/frontend/entities-structure.md` ("Generated types in
`domain/`" and the Layer Rules enforcement note) rather than as ADRs.

## Knowledge Updated

- dev/knowledge/frontend/entities-structure.md (Classifying a file into `domain/` — type-placement litmus)
- dev/knowledge/frontend/entities-structure.md (Layer Rules — review-only enforcement note)
- dev/knowledge/frontend/entities-structure.md (Known exceptions — path-traversal HIDDEN_NAMESPACES, object-table utils/, relationships api→use-case edge)

## Guidelines Updated

- dev/guidelines/frontend/typescript.md (The TypeScript gate is `betterer`, not `tsc`)

## Notes

- Most of `doc-updates-pending.md` had already been applied to `entities-structure.md` during the
  migration itself; only the deltas above were still missing. Several debt items listed there were
  verified already resolved in the tree (`nodes/` loose files, all `utils/` directories except
  `nodes/object/ui/object-table/utils/`) and were extracted accordingly.
- research.md D8 (rollout order) and D9 (branching) were skipped as one-off execution decisions.

## Archive

Spec directory moved to `specs/archive/001-entities-arch-migration/` as a historical record.
