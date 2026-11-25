# Checks pipeline scope

> Part of: `dev/guidelines/` | Related: [Backend checklist](backend/checklist.md)

Before changing Infrahub's proposed-change checks or CI pipeline, investigate whether the same
behavior applies to other validator and check types. This guideline covers the product's validation
pipeline; repository build and test workflows have separate concerns.

- Compare artifact, data, generator, repository, schema, and user validators. Include related
  background work when it shares the behavior being changed.
- Trace the shared schema, API, execution, and UI paths before adding a type-specific path. Check
  whether inputs, result states, permissions, and lifecycle semantics support the same behavior.
- Implement common behavior at the shared layer when it fits. Keep type-specific behavior where
  its contract differs; shared presentation does not establish shared execution or retry semantics.
- Record which cases benefit and why any remain excluded in the design or PR description. Test
  representative types through the shared path and cover any meaningful differences. Investigating
  adjacent cases does not require implementing unrelated features.

For example, when adding failed-first ordering to artifact checks, inspect the shared
`CoreValidator.checks` relationship and `CoreCheck.conclusion` before choosing an artifact-only
query. If the same ordering applies to other validators, cover them through the shared query and
verify ordering across pagination. Assess retry eligibility separately from result ordering.
