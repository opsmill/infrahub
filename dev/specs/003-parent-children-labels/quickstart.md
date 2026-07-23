# Quickstart / Validation Guide

Validates that hierarchical `parent`/`children` relationships render the peer kind's label instead of "Parent"/"Children".

## Prerequisites

- Frontend deps installed: `cd frontend/app && pnpm install`
- A running Infrahub with demo data containing a hierarchical object whose parent peer has a label (e.g. a Location hierarchy: `Region` → `Site`, or an IPAM prefix hierarchy).

## Unit validation (fast, no backend)

```bash
cd frontend/app && pnpm test src/entities/schema/domain/rules/get-relationship-field-label.test.ts
```

Expected: all contract cases pass — see [contracts/get-relationship-field-label.md](./contracts/get-relationship-field-label.md) (C1–C4).

## Manual validation

1. Open a hierarchical object (e.g. a `Site` whose parent is a `Region`).
2. **Detail view**: the parent field heading reads the peer label (e.g. "Region"), not "Parent".
3. **Tabs**: the children tab reads the peer label, not "Children".
4. **Table**: list the hierarchical kind; the parent/children column header reads the peer label.
5. **Filters**: open filters; the relationship filter heading reads the peer label.
6. **Sort**: open the sort picker; the parent/children entry reads the peer label.
7. **Regression**: a non-hierarchical relationship (e.g. an object's `tags`) is unchanged.

## E2E validation (constitution IV — required)

```bash
cd frontend/app && pnpm test:e2e <hierarchical-object-label>.spec.ts
```

Expected: the E2E navigates to a hierarchical object and asserts the parent/children label equals the peer kind's label, not "Parent"/"Children".

## Full local CI gate before pushing

```bash
cd frontend/app && pnpm exec biome ci . && pnpm knip && pnpm exec betterer ci && pnpm test
```
