# Path traversal — forms refactor implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the path-traversal feature's hand-rolled forms, page, and `useSearchParams` plumbing with `react-hook-form` (RHF) + `nuqs` URL state + per-mode panels, and add UUID auto-detect to the shared `RelationshipComboboxList` so the `ObjectPicker` can drop its mode toggle.

**Architecture:** URL is canonical (per-mode `useQueryStates` hook). RHF reads URL via `defaultValues` + `values`, so back/forward auto-resyncs the form without `useEffect`. Submit writes URL; query is enabled iff URL has required fields, so deep-linked URLs auto-run on first load. Page collapses to chrome (header + mode tabs + panel slot); each mode owns a `panel.tsx` (form + query + results), `form.tsx`, `results.tsx`, `use-*-mode-params.ts`.

**Tech Stack:** React 19, TypeScript 5.9, react-hook-form, nuqs, @tanstack/react-query, Vitest 4.1, Playwright 1.56. Uses `Form` / `FormField` / `FormInput` / `FormMessage` / `FormSubmit` from `frontend/app/src/shared/components/ui/form.tsx`, `Accordion` from `frontend/app/src/shared/components/ui/accordion.tsx`, `Input` from `frontend/app/src/shared/components/ui/input.tsx`, `Label` from `frontend/app/src/shared/components/ui/label.tsx`, `Button` / `Spinner` from `@infrahub/ui`, `KindMultiSelect` and `NodeKindSelect` from `frontend/app/src/shared/components/inputs/`, `PeerInput` from `frontend/app/src/shared/components/inputs/peer.tsx`.

**Reference docs:**
- `dev/specs/infp-1991-graph-path-traversal/forms-refactor-design.md` — the spec this plan implements.
- `dev/specs/infp-1991-graph-path-traversal/frontend-review.md` — original review.
- `dev/guidelines/frontend/component-patterns.md`, `dev/guidelines/frontend/page-architecture.md`, `dev/guidelines/frontend/object-forms.md` — coding guidelines.
- `dev/guides/frontend/writing-component-tests.md`, `dev/guides/frontend/writing-e2e-tests.md` — how to write tests.

**Boundaries (apply to every task):**
- Frontend-only. Do not edit backend, GraphQL schema, or `pnpm-lock.yaml`.
- Run `cd frontend/app && pnpm biome:fix` after edits, before each commit.
- Never use `git commit --no-verify`.
- Each task's commit must keep `cd frontend/app && pnpm test -- --run` and `cd frontend/app && pnpm tsc --noEmit` green.

---

## Task overview

| # | Subject | Files |
|---|---|---|
| 1 | `is-uuid` helper + tests | `shared/utils/is-uuid.ts`, `shared/utils/is-uuid.test.ts` |
| 2 | UUID auto-detect in `RelationshipComboboxList` + tests | `entities/nodes/relationships/ui/relationship-combobox-list.tsx`, `relationship-combobox-list.test.tsx` |
| 3 | Move pure formatters to `format-paths.ts` + tests | `entities/path-traversal/ui/format-paths.ts`, `format-paths.test.ts`, `path-traversal-page.tsx` |
| 4 | Simplify `ObjectPicker` (drop mode toggle, id-only API) + update its callers | `entities/path-traversal/ui/object-picker.tsx`, `object-selector.tsx`, `dependency-selector.tsx` |
| 5 | Path-mode folder: URL hook + form + panel + results | `entities/path-traversal/ui/path-mode/*` (4 new files) |
| 6 | Dependencies-mode folder: URL hook + form + panel + results | `entities/path-traversal/ui/dependencies-mode/*` (4 new files) |
| 7 | Wire panels into `path-traversal-page.tsx`; remove old selectors | `entities/path-traversal/ui/path-traversal-page.tsx`; delete `object-selector.tsx`, `dependency-selector.tsx` |
| 8 | Object-shaped cache key for path-traversal | `entities/path-traversal/domain/path-traversal.query-keys.ts`, `path-traversal.query.ts`, callers |
| 9 | E2E coverage bump | `frontend/app/tests/e2e/path-traversal.spec.ts` |

Each task ends with a commit. Earlier tasks are deliberately "no behavior change" so the page keeps rendering until task 7.

---

## Task 1: `is-uuid` helper

**Files:**
- Create: `frontend/app/src/shared/utils/is-uuid.ts`
- Create: `frontend/app/src/shared/utils/is-uuid.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/app/src/shared/utils/is-uuid.test.ts`:

```ts
import { describe, expect, test } from "vitest";

import { isUuid } from "./is-uuid";

describe("isUuid", () => {
  test("accepts a canonical lowercase v4 UUID", () => {
    expect(isUuid("17a4cdef-1234-4abc-8def-0123456789ab")).toBe(true);
  });

  test("accepts mixed-case", () => {
    expect(isUuid("17A4CDEF-1234-4abc-8DEF-0123456789AB")).toBe(true);
  });

  test("trims surrounding whitespace", () => {
    expect(isUuid("  17a4cdef-1234-4abc-8def-0123456789ab \n")).toBe(true);
  });

  test("rejects empty string", () => {
    expect(isUuid("")).toBe(false);
  });

  test("rejects missing dashes", () => {
    expect(isUuid("17a4cdef12344abc8def0123456789ab")).toBe(false);
  });

  test("rejects extra characters", () => {
    expect(isUuid("foo-17a4cdef-1234-4abc-8def-0123456789ab")).toBe(false);
    expect(isUuid("17a4cdef-1234-4abc-8def-0123456789ab-bar")).toBe(false);
  });

  test("rejects partial UUID", () => {
    expect(isUuid("17a4cdef-1234")).toBe(false);
  });

  test("rejects non-hex characters", () => {
    expect(isUuid("zzzzzzzz-1234-4abc-8def-0123456789ab")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/app && pnpm test -- --run src/shared/utils/is-uuid.test.ts`
Expected: FAIL with `Cannot find module './is-uuid'` or similar.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/app/src/shared/utils/is-uuid.ts`:

```ts
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const isUuid = (value: string): boolean => UUID_RE.test(value.trim());
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend/app && pnpm test -- --run src/shared/utils/is-uuid.test.ts`
Expected: PASS, 8 tests.

- [ ] **Step 5: Lint and commit**

```bash
cd frontend/app && pnpm biome:fix src/shared/utils/is-uuid.ts src/shared/utils/is-uuid.test.ts
cd /Users/paul/Projects/infrahub
git add frontend/app/src/shared/utils/is-uuid.ts frontend/app/src/shared/utils/is-uuid.test.ts
git commit -m "feat(shared): add isUuid helper"
```

---

## Task 2: UUID auto-detect in `RelationshipComboboxList`

**Files:**
- Modify: `frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.tsx`
- Create: `frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { RelationshipComboboxList } from "./relationship-combobox-list";

const useRelationshipsMock = vi.fn();
const useSchemaMock = vi.fn();

vi.mock("@/entities/nodes/relationships/ui/queries/get-relationships.query", () => ({
  useRelationships: (args: unknown) => useRelationshipsMock(args),
}));
vi.mock("@/entities/schema/ui/hooks/useSchema", () => ({
  useSchema: () => useSchemaMock(),
}));
vi.mock("@/shared/utils/common", () => ({
  classNames: (...args: unknown[]) => args.filter(Boolean).join(" "),
  debounce: (fn: (...args: unknown[]) => unknown) => fn,
}));

function setupReturn() {
  return {
    isPending: false,
    data: { pages: [[]] },
    error: null,
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
  };
}

describe("RelationshipComboboxList", () => {
  test("uses the search filter for non-UUID queries", async () => {
    useRelationshipsMock.mockReturnValue(setupReturn());
    useSchemaMock.mockReturnValue({ schema: { label: "Device" } });

    render(<RelationshipComboboxList peer="InfraDevice" onSelect={vi.fn()} />);

    const input = screen.getByRole("combobox");
    await userEvent.type(input, "router-1");

    const lastCall = useRelationshipsMock.mock.calls.at(-1)?.[0];
    expect(lastCall).toEqual({
      peer: "InfraDevice",
      search: "router-1",
      filterQuery: undefined,
    });
  });

  test("switches to ids filter when search is a UUID", async () => {
    useRelationshipsMock.mockReturnValue(setupReturn());
    useSchemaMock.mockReturnValue({ schema: { label: "Device" } });

    render(<RelationshipComboboxList peer="InfraDevice" onSelect={vi.fn()} />);

    const input = screen.getByRole("combobox");
    await userEvent.type(input, "17a4cdef-1234-4abc-8def-0123456789ab");

    const lastCall = useRelationshipsMock.mock.calls.at(-1)?.[0];
    expect(lastCall).toEqual({
      peer: "InfraDevice",
      search: undefined,
      filterQuery: { ids: ["17a4cdef-1234-4abc-8def-0123456789ab"] },
    });
  });

  test("UUID match overrides a caller-provided filterQuery", async () => {
    useRelationshipsMock.mockReturnValue(setupReturn());
    useSchemaMock.mockReturnValue({ schema: { label: "Device" } });

    render(
      <RelationshipComboboxList
        peer="InfraDevice"
        onSelect={vi.fn()}
        filterQuery={{ parent__ids: ["zzz"] }}
      />
    );

    const input = screen.getByRole("combobox");
    await userEvent.type(input, "17a4cdef-1234-4abc-8def-0123456789ab");

    const lastCall = useRelationshipsMock.mock.calls.at(-1)?.[0];
    expect(lastCall.filterQuery).toEqual({ ids: ["17a4cdef-1234-4abc-8def-0123456789ab"] });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/app && pnpm test -- --run src/entities/nodes/relationships/ui/relationship-combobox-list.test.tsx`
Expected: FAIL — second test sees `search: "17a4cdef-..."` instead of the `ids` filter, since auto-detect isn't wired yet.

- [ ] **Step 3: Modify the component**

Open `frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.tsx` and:

1. Add the import (top of file, with the other `@/shared/utils/...` imports):

```ts
import { isUuid } from "@/shared/utils/is-uuid";
```

2. Replace the `useRelationships` call so it branches on whether `search` looks like a UUID. The existing call site is:

```ts
const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
  useRelationships({ peer, search, filterQuery });
```

Change it to:

```ts
// When the user types or pastes a UUID, switch the underlying query from a
// label search to an ids filter. UUID is a maximally specific match, so it
// intentionally overrides any caller-provided filterQuery.
const isUuidSearch = search.length > 0 && isUuid(search);
const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
  useRelationships({
    peer,
    search: isUuidSearch ? undefined : search,
    filterQuery: isUuidSearch ? { ids: [search.trim()] } : filterQuery,
  });
```

- [ ] **Step 4: Run tests to verify all three pass**

Run: `cd frontend/app && pnpm test -- --run src/entities/nodes/relationships/ui/relationship-combobox-list.test.tsx`
Expected: PASS, 3 tests.

- [ ] **Step 5: Lint, run full unit suite, commit**

```bash
cd frontend/app && pnpm biome:fix src/entities/nodes/relationships/ui/relationship-combobox-list.tsx src/entities/nodes/relationships/ui/relationship-combobox-list.test.tsx
cd frontend/app && pnpm test -- --run
cd frontend/app && pnpm tsc --noEmit
cd /Users/paul/Projects/infrahub
git add frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.tsx frontend/app/src/entities/nodes/relationships/ui/relationship-combobox-list.test.tsx
git commit -m "feat(relationships): auto-detect UUID search and switch to ids filter"
```

---

## Task 3: Move pure formatters out of the page

**Files:**
- Create: `frontend/app/src/entities/path-traversal/ui/format-paths.ts`
- Create: `frontend/app/src/entities/path-traversal/ui/format-paths.test.ts`
- Modify: `frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/app/src/entities/path-traversal/ui/format-paths.test.ts`:

```ts
import { describe, expect, test } from "vitest";

import type { PathResult, PathTraversalResponse } from "../domain/get-path-traversal";
import {
  copyAllPathsAsText,
  formatPathAsText,
  getKindCounts,
  pathPreview,
} from "./format-paths";

const a = { id: "a", kind: "InfraDevice", display_label: "router-1" };
const b = { id: "b", kind: "InfraInterface", display_label: "Ethernet1" };
const c = { id: "c", kind: "InfraDevice", display_label: "router-2" };

const rel = (name: string) => ({ id: `r-${name}`, name, direction: "OUTBOUND" as const });

const path: PathResult = {
  objects: [a, b, c],
  relationships: [rel("device__interfaces"), rel("interface__device")],
  depth: 2,
};

const response: PathTraversalResponse = {
  paths: [path],
  source: a,
  destination: c,
  total_paths_found: 1,
};

describe("formatPathAsText", () => {
  test("renders objects joined by relationship names", () => {
    expect(formatPathAsText(response, 0)).toBe(
      "router-1 -[device / interfaces]-> Ethernet1 -[interface / device]-> router-2"
    );
  });

  test("falls back to a plain arrow when a relationship is missing", () => {
    const broken: PathTraversalResponse = {
      ...response,
      paths: [{ ...path, relationships: [rel("device__interfaces")] }],
    };
    expect(formatPathAsText(broken, 0)).toBe(
      "router-1 -[device / interfaces]-> Ethernet1  ->  router-2"
    );
  });

  test("returns empty string for an out-of-range path index", () => {
    expect(formatPathAsText(response, 5)).toBe("");
  });
});

describe("copyAllPathsAsText", () => {
  test("renders one numbered line per path", () => {
    const data: PathTraversalResponse = {
      ...response,
      paths: [path, { ...path, objects: [a, c], relationships: [rel("foo")], depth: 1 }],
      total_paths_found: 2,
    };
    expect(copyAllPathsAsText(data)).toBe(
      "Path 1: router-1 → Ethernet1 → router-2\nPath 2: router-1 → router-2"
    );
  });

  test("returns empty string for zero paths", () => {
    expect(copyAllPathsAsText({ ...response, paths: [], total_paths_found: 0 })).toBe("");
  });
});

describe("pathPreview", () => {
  test("returns the full chain when objects fit under the limit", () => {
    expect(pathPreview(path, 5)).toBe("router-1 -> Ethernet1 -> router-2");
  });

  test("returns first -> ... -> last when objects exceed the limit", () => {
    const longPath: PathResult = {
      ...path,
      objects: [a, b, c, { ...a, id: "d", display_label: "router-3" }],
    };
    expect(pathPreview(longPath, 3)).toBe("router-1 -> ... -> router-3");
  });

  test("uses default limit of 3", () => {
    expect(pathPreview(path)).toBe("router-1 -> Ethernet1 -> router-2");
  });
});

describe("getKindCounts", () => {
  test("counts and labels each kind on the path", () => {
    expect(getKindCounts(path)).toBe("2x InfraDevice, 1x InfraInterface");
  });

  test("returns an empty string for a path with no objects", () => {
    expect(getKindCounts({ ...path, objects: [] })).toBe("");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/app && pnpm test -- --run src/entities/path-traversal/ui/format-paths.test.ts`
Expected: FAIL with `Cannot find module './format-paths'`.

- [ ] **Step 3: Create the module by extracting from `path-traversal-page.tsx`**

Create `frontend/app/src/entities/path-traversal/ui/format-paths.ts`:

```ts
import type { PathResult, PathTraversalResponse } from "../domain/get-path-traversal";
import { formatRelName } from "./utils";

export function formatPathAsText(data: PathTraversalResponse, pathIndex: number): string {
  const path = data.paths[pathIndex];
  if (!path) return "";
  const objectLabels = path.objects.map((o) => o.display_label);
  const parts: string[] = [];
  for (let i = 0; i < objectLabels.length; i++) {
    parts.push(objectLabels[i] ?? "");
    if (i < objectLabels.length - 1) {
      const rel = path.relationships[i];
      if (rel) {
        parts.push(`-[${formatRelName(rel.name)}]->`);
      } else {
        parts.push(" -> ");
      }
    }
  }
  return parts.join(" ");
}

export function copyAllPathsAsText(data: PathTraversalResponse): string {
  return data.paths
    .map((path, i) => `Path ${i + 1}: ${path.objects.map((o) => o.display_label).join(" → ")}`)
    .join("\n");
}

export function pathPreview(path: PathResult, maxObjects = 3): string {
  const names = path.objects.map((o) => o.display_label);
  if (names.length <= maxObjects) return names.join(" -> ");
  const first = names[0];
  const last = names.at(-1);
  return `${first} -> ... -> ${last}`;
}

export function getKindCounts(path: PathResult): string {
  const counts = new Map<string, number>();
  for (const object of path.objects) {
    counts.set(object.kind, (counts.get(object.kind) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([kind, count]) => `${count}x ${kind}`)
    .join(", ");
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend/app && pnpm test -- --run src/entities/path-traversal/ui/format-paths.test.ts`
Expected: PASS, 9 tests.

- [ ] **Step 5: Update `path-traversal-page.tsx` to import from the new module**

Open `frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx`:

1. Delete the four function definitions: `formatPathAsText`, `copyAllPathsAsText`, `pathPreview`, `getKindCounts` (lines 14–55 of the current file).
2. Update the existing import block. The current line:

```ts
import { formatRelName, getKindColor } from "./utils";
```

becomes:

```ts
import { copyAllPathsAsText, formatPathAsText, getKindCounts, pathPreview } from "./format-paths";
import { getKindColor } from "./utils";
```

(Note: `formatRelName` is no longer needed in the page; it's only used inside `format-paths.ts` now.)

- [ ] **Step 6: Run typecheck and full unit suite**

Run: `cd frontend/app && pnpm tsc --noEmit && pnpm test -- --run`
Expected: green.

- [ ] **Step 7: Lint and commit**

```bash
cd frontend/app && pnpm biome:fix src/entities/path-traversal/ui/format-paths.ts src/entities/path-traversal/ui/format-paths.test.ts src/entities/path-traversal/ui/path-traversal-page.tsx
cd /Users/paul/Projects/infrahub
git add frontend/app/src/entities/path-traversal/ui/format-paths.ts frontend/app/src/entities/path-traversal/ui/format-paths.test.ts frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx
git commit -m "refactor(path-traversal): move pure formatters into format-paths module"
```

---

## Task 4: Simplify `ObjectPicker` (drop mode toggle, id-only API)

**Files:**
- Modify: `frontend/app/src/entities/path-traversal/ui/object-picker.tsx`
- Modify: `frontend/app/src/entities/path-traversal/ui/object-selector.tsx`
- Modify: `frontend/app/src/entities/path-traversal/ui/dependency-selector.tsx`

This task changes `ObjectPicker`'s API to id-only and drops its mode toggle. Both legacy selectors (still in place — they're replaced in Task 7) need to be updated to match the new prop shape so the page keeps rendering.

- [ ] **Step 1: Replace `object-picker.tsx`**

Open `frontend/app/src/entities/path-traversal/ui/object-picker.tsx`. Replace the entire file with:

```tsx
import { Button } from "@infrahub/ui";
import { useState } from "react";

import { NodeKindSelect } from "@/shared/components/inputs/node-kind-select";
import { PeerInput } from "@/shared/components/inputs/peer";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import type { ModelSchema } from "@/entities/schema/types";

import { isVisibleNamespace } from "./utils";

type ObjectPickerProps = {
  label: string;
  value: string;
  onChange: (id: string) => void;
};

export function ObjectPicker({ label, value, onChange }: ObjectPickerProps) {
  const [selectedKind, setSelectedKind] = useState<string | null>(null);

  // Resolve the display label whenever the picker has a value but no
  // selection in flight. Cheap when cached by React Query.
  const { data: resolved } = useGetObject(
    { objectId: value, objectSchema: { kind: "CoreNode" } as ModelSchema },
    { enabled: !!value }
  );

  const peerValue: Node | null = value
    ? {
        id: value,
        display_label: resolved?.display_label ?? value,
        __typename: selectedKind ?? "",
      }
    : null;

  return (
    <div className="space-y-1.5">
      <span className="block font-medium text-gray-700 text-sm">{label}</span>

      <NodeKindSelect
        value={selectedKind}
        onChange={setSelectedKind}
        filter={isVisibleNamespace}
        className="w-full"
      />

      <PeerInput
        peer={selectedKind ?? "CoreNode"}
        value={peerValue}
        onChange={(node) => onChange(node?.id ?? "")}
        className="w-full"
        placeholder="Search by name, or paste an object ID"
      />

      {value && (
        <div className="flex items-center gap-2 rounded bg-blue-50 px-2 py-1.5">
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium text-blue-800 text-xs">
              {resolved?.display_label ?? value}
            </div>
            <div className="truncate font-mono text-blue-600 text-xs">{value}</div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange("");
              setSelectedKind(null);
            }}
          >
            Clear
          </Button>
        </div>
      )}
    </div>
  );
}
```

Notes for the engineer:
- `isVisibleNamespace` is already exported from `./utils`.
- `PeerInput` accepts a `placeholder` prop via the spread `PopoverTriggerProps`. If TypeScript complains that `placeholder` is not a known prop, omit it — the existing `RelationshipComboboxList`'s search input has its own placeholder handling. The unit test for Task 4 does not assert placeholder text.
- `Button` from `@infrahub/ui` accepts `variant="ghost"` and `size="sm"` per `frontend/packages/ui/src/components/button/button.tsx:85` (`ButtonProps`).

- [ ] **Step 2: Update `object-selector.tsx` to the new `ObjectPicker` API**

Open `frontend/app/src/entities/path-traversal/ui/object-selector.tsx` and replace the file with:

```tsx
import { type FormEvent, useState } from "react";

import { KindMultiSelect } from "@/shared/components/inputs/kind-multi-select";

import { ObjectPicker } from "./object-picker";
import { isVisibleNamespace } from "./utils";

type SearchParams = {
  sourceId: string;
  destinationId: string;
  maxDepth: number;
  maxPaths: number;
  kindFilter: string[];
  excludedKinds: string[];
};

type ObjectSelectorProps = {
  onSearch: (params: SearchParams) => void;
  isLoading: boolean;
  initialSourceId?: string;
  initialDestinationId?: string;
  maxDepth?: number;
  maxPaths?: number;
  excludedKinds?: string[];
  onMaxDepthChange?: (value: number) => void;
  onMaxPathsChange?: (value: number) => void;
  onExcludedKindsChange?: (kinds: string[]) => void;
};

export function ObjectSelector({
  onSearch,
  isLoading,
  initialSourceId = "",
  initialDestinationId = "",
  maxDepth = 5,
  maxPaths = 10,
  excludedKinds = [],
  onMaxDepthChange,
  onMaxPathsChange,
  onExcludedKindsChange,
}: ObjectSelectorProps) {
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [destinationId, setDestinationId] = useState(initialDestinationId);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedKinds, setSelectedKinds] = useState<string[]>([]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (sourceId && destinationId) {
      onSearch({
        sourceId,
        destinationId,
        maxDepth,
        maxPaths,
        kindFilter: selectedKinds,
        excludedKinds,
      });
    }
  }

  function handleSwap() {
    const prev = sourceId;
    setSourceId(destinationId);
    setDestinationId(prev);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4">
      <ObjectPicker label="Source Object" value={sourceId} onChange={setSourceId} />

      {(sourceId || destinationId) && (
        <button
          type="button"
          onClick={handleSwap}
          className="flex w-full items-center justify-center gap-1 rounded border border-gray-200 px-3 py-1 text-gray-500 text-xs hover:bg-gray-50"
        >
          ⇅ Swap
        </button>
      )}

      <ObjectPicker label="Destination Object" value={destinationId} onChange={setDestinationId} />

      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-blue-600 text-sm hover:text-blue-800"
      >
        {showAdvanced ? "Hide" : "Show"} Advanced Options
      </button>

      {showAdvanced && (
        <div className="space-y-3 rounded-md border border-gray-200 p-3">
          <div className="flex gap-4">
            <div className="flex-1">
              <label htmlFor="max-depth" className="block font-medium text-gray-600 text-xs">
                Max Depth
              </label>
              <input
                id="max-depth"
                type="number"
                min={1}
                max={20}
                value={maxDepth}
                onChange={(e) => onMaxDepthChange?.(Number(e.target.value))}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <div className="flex-1">
              <label htmlFor="max-paths" className="block font-medium text-gray-600 text-xs">
                Max Paths
              </label>
              <input
                id="max-paths"
                type="number"
                min={1}
                max={100}
                value={maxPaths}
                onChange={(e) => onMaxPathsChange?.(Number(e.target.value))}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

          <KindMultiSelect
            value={selectedKinds}
            onChange={setSelectedKinds}
            label="Include only these kinds"
            filter={isVisibleNamespace}
          />

          <KindMultiSelect
            value={excludedKinds}
            onChange={(kinds) => onExcludedKindsChange?.(kinds)}
            label="Exclude kinds"
            placeholder="Search kinds to exclude..."
            showChips
            chipTone="red"
            filter={isVisibleNamespace}
          />
        </div>
      )}

      <button
        type="submit"
        disabled={isLoading || !sourceId || !destinationId}
        className="w-full rounded-md bg-blue-600 px-4 py-2 font-medium text-sm text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {isLoading ? "Finding Paths..." : "Find Paths"}
      </button>
    </form>
  );
}
```

The diff vs. the current file: removed `sourceLabel` / `destinationLabel` `useState`, removed `displayLabel` props on `ObjectPicker`, simplified `onChange` handlers to id-only.

- [ ] **Step 3: Update `dependency-selector.tsx` to the new `ObjectPicker` API**

Open `frontend/app/src/entities/path-traversal/ui/dependency-selector.tsx` and replace the file with:

```tsx
import { type FormEvent, useState } from "react";

import { KindMultiSelect } from "@/shared/components/inputs/kind-multi-select";

import { ObjectPicker } from "./object-picker";
import { isVisibleNamespace } from "./utils";

type DependencySelectorProps = {
  onSearch: (params: { sourceId: string; targetKinds: string[]; maxDepth: number }) => void;
  isLoading: boolean;
  initialSourceId?: string;
};

export function DependencySelector({
  onSearch,
  isLoading,
  initialSourceId = "",
}: DependencySelectorProps) {
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [selectedKinds, setSelectedKinds] = useState<string[]>([]);
  const [maxDepth, setMaxDepth] = useState(5);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (sourceId && selectedKinds.length > 0) {
      onSearch({ sourceId, targetKinds: selectedKinds, maxDepth });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4">
      <ObjectPicker label="Source Object" value={sourceId} onChange={setSourceId} />

      <KindMultiSelect
        value={selectedKinds}
        onChange={setSelectedKinds}
        label="What kinds to find?"
        filter={isVisibleNamespace}
      />

      <div>
        <label htmlFor="deps-depth" className="block font-medium text-gray-600 text-xs">
          Max Depth
        </label>
        <input
          id="deps-depth"
          type="number"
          min={1}
          max={20}
          value={maxDepth}
          onChange={(e) => setMaxDepth(Number(e.target.value))}
          className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <button
        type="submit"
        disabled={isLoading || !sourceId || selectedKinds.length === 0}
        className="w-full rounded-md bg-amber-600 px-4 py-2 font-medium text-sm text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {isLoading ? "Searching..." : "Find Dependencies"}
      </button>
    </form>
  );
}
```

Diff vs. the current file: removed `sourceLabel` `useState` and the `displayLabel` prop on `ObjectPicker`.

- [ ] **Step 4: Verify the page still typechecks and renders**

Run: `cd frontend/app && pnpm tsc --noEmit`
Expected: no errors. If `path-traversal-page.tsx` still passes `initialSourceId` / `initialDestinationId` to `ObjectSelector` / `DependencySelector` — it does, those props are unchanged — the page should compile cleanly.

Run: `cd frontend/app && pnpm test -- --run`
Expected: all green.

Manual check (in dev server or skip if not viable for this step): navigate to `/path-traversal`, confirm the picker still renders kind dropdown + search input + clear chip when a value is set.

- [ ] **Step 5: Lint and commit**

```bash
cd frontend/app && pnpm biome:fix src/entities/path-traversal/ui/object-picker.tsx src/entities/path-traversal/ui/object-selector.tsx src/entities/path-traversal/ui/dependency-selector.tsx
cd /Users/paul/Projects/infrahub
git add frontend/app/src/entities/path-traversal/ui/object-picker.tsx frontend/app/src/entities/path-traversal/ui/object-selector.tsx frontend/app/src/entities/path-traversal/ui/dependency-selector.tsx
git commit -m "refactor(path-traversal): drop ObjectPicker mode toggle, switch to id-only API"
```

---

## Task 5: Path-mode folder

**Files:**
- Create: `frontend/app/src/entities/path-traversal/ui/path-mode/use-path-mode-params.ts`
- Create: `frontend/app/src/entities/path-traversal/ui/path-mode/use-path-mode-params.test.ts`
- Create: `frontend/app/src/entities/path-traversal/ui/path-mode/path-mode-form.tsx`
- Create: `frontend/app/src/entities/path-traversal/ui/path-mode/path-mode-results.tsx`
- Create: `frontend/app/src/entities/path-traversal/ui/path-mode/path-mode-panel.tsx`

Path-mode is implemented as four files. The form and results modules are pure UI. The panel wires URL state, RHF, and React Query together. The URL-state hook + its mappers are tested in isolation.

- [ ] **Step 1: Write the failing test for the URL-mapper helpers**

Create `frontend/app/src/entities/path-traversal/ui/path-mode/use-path-mode-params.test.ts`:

```ts
import { describe, expect, test } from "vitest";

import { formValuesToParams, paramsToFormValues } from "./use-path-mode-params";

describe("paramsToFormValues", () => {
  test("maps URL params to form values", () => {
    expect(
      paramsToFormValues({
        source: "src-id",
        destination: "dst-id",
        depth: 7,
        maxPaths: 25,
        kindFilter: ["InfraDevice"],
        excludedKinds: ["InfraInterface"],
        selectedPath: 3,
      })
    ).toEqual({
      sourceId: "src-id",
      destinationId: "dst-id",
      maxDepth: 7,
      maxPaths: 25,
      kindFilter: ["InfraDevice"],
      excludedKinds: ["InfraInterface"],
    });
  });
});

describe("formValuesToParams", () => {
  test("maps form values to URL param updates and resets selectedPath", () => {
    expect(
      formValuesToParams({
        sourceId: "src-id",
        destinationId: "dst-id",
        maxDepth: 4,
        maxPaths: 12,
        kindFilter: ["InfraDevice"],
        excludedKinds: [],
      })
    ).toEqual({
      source: "src-id",
      destination: "dst-id",
      depth: 4,
      maxPaths: 12,
      kindFilter: ["InfraDevice"],
      excludedKinds: [],
      selectedPath: 0,
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/app && pnpm test -- --run src/entities/path-traversal/ui/path-mode/use-path-mode-params.test.ts`
Expected: FAIL with `Cannot find module './use-path-mode-params'`.

- [ ] **Step 3: Implement `use-path-mode-params.ts`**

Create `frontend/app/src/entities/path-traversal/ui/path-mode/use-path-mode-params.ts`:

```ts
import {
  parseAsInteger,
  parseAsNativeArrayOf,
  parseAsString,
  useQueryStates,
} from "nuqs";

export const PATH_MODE_PARAMS = {
  source: parseAsString.withDefault(""),
  destination: parseAsString.withDefault(""),
  depth: parseAsInteger.withDefault(5),
  maxPaths: parseAsInteger.withDefault(10),
  kindFilter: parseAsNativeArrayOf(parseAsString).withDefault([]),
  excludedKinds: parseAsNativeArrayOf(parseAsString).withDefault([]),
  selectedPath: parseAsInteger.withDefault(0),
} as const;

export type PathModeParams = {
  source: string;
  destination: string;
  depth: number;
  maxPaths: number;
  kindFilter: string[];
  excludedKinds: string[];
  selectedPath: number;
};

export type PathModeFormValues = {
  sourceId: string;
  destinationId: string;
  maxDepth: number;
  maxPaths: number;
  kindFilter: string[];
  excludedKinds: string[];
};

export function paramsToFormValues(p: PathModeParams): PathModeFormValues {
  return {
    sourceId: p.source,
    destinationId: p.destination,
    maxDepth: p.depth,
    maxPaths: p.maxPaths,
    kindFilter: p.kindFilter,
    excludedKinds: p.excludedKinds,
  };
}

export function formValuesToParams(v: PathModeFormValues): Partial<PathModeParams> {
  return {
    source: v.sourceId,
    destination: v.destinationId,
    depth: v.maxDepth,
    maxPaths: v.maxPaths,
    kindFilter: v.kindFilter,
    excludedKinds: v.excludedKinds,
    selectedPath: 0,
  };
}

export function usePathModeParams() {
  return useQueryStates(PATH_MODE_PARAMS, { history: "push" });
}
```

- [ ] **Step 4: Run helper test to verify it passes**

Run: `cd frontend/app && pnpm test -- --run src/entities/path-traversal/ui/path-mode/use-path-mode-params.test.ts`
Expected: PASS, 2 tests.

- [ ] **Step 5: Implement `path-mode-form.tsx`**

Create `frontend/app/src/entities/path-traversal/ui/path-mode/path-mode-form.tsx`:

```tsx
import { Button } from "@infrahub/ui";
import type { UseFormReturn } from "react-hook-form";

import { KindMultiSelect } from "@/shared/components/inputs/kind-multi-select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/shared/components/ui/accordion";
import { Form, FormField, FormInput, FormLabel, FormMessage, FormSubmit } from "@/shared/components/ui/form";
import Input from "@/shared/components/ui/input";

import { ObjectPicker } from "../object-picker";
import { isVisibleNamespace } from "../utils";
import type { PathModeFormValues } from "./use-path-mode-params";

type PathModeFormProps = {
  form: UseFormReturn<PathModeFormValues>;
  onSubmit: (values: PathModeFormValues) => void;
  isPending: boolean;
};

export function PathModeForm({ form, onSubmit, isPending }: PathModeFormProps) {
  const sourceId = form.watch("sourceId");
  const destinationId = form.watch("destinationId");

  function handleSwap() {
    form.setValue("sourceId", destinationId, { shouldDirty: true });
    form.setValue("destinationId", sourceId, { shouldDirty: true });
  }

  return (
    <Form
      form={form as unknown as UseFormReturn}
      onSubmit={(values) => onSubmit(values as PathModeFormValues)}
      className="p-4"
    >
      <FormField
        name="sourceId"
        rules={{ required: "Source is required" }}
        render={({ field }) => (
          <div className="space-y-1">
            <ObjectPicker
              label="Source Object"
              value={(field.value as string) ?? ""}
              onChange={field.onChange}
            />
            <FormMessage />
          </div>
        )}
      />

      {(sourceId || destinationId) && (
        <Button variant="ghost" onClick={handleSwap} className="w-full">
          ⇅ Swap
        </Button>
      )}

      <FormField
        name="destinationId"
        rules={{ required: "Destination is required" }}
        render={({ field }) => (
          <div className="space-y-1">
            <ObjectPicker
              label="Destination Object"
              value={(field.value as string) ?? ""}
              onChange={field.onChange}
            />
            <FormMessage />
          </div>
        )}
      />

      <Accordion type="single" collapsible>
        <AccordionItem value="advanced">
          <AccordionTrigger>Advanced options</AccordionTrigger>
          <AccordionContent className="space-y-3">
            <div className="flex gap-4">
              <div className="flex-1 space-y-1">
                <FormField
                  name="maxDepth"
                  rules={{
                    required: "Max depth is required",
                    min: { value: 1, message: "Must be ≥ 1" },
                    max: { value: 20, message: "Must be ≤ 20" },
                    valueAsNumber: true,
                  }}
                  render={({ field }) => (
                    <>
                      <FormLabel>Max Depth</FormLabel>
                      <FormInput>
                        <Input
                          type="number"
                          min={1}
                          max={20}
                          value={(field.value as number) ?? 5}
                          onChange={(e) => field.onChange(Number(e.target.value))}
                        />
                      </FormInput>
                      <FormMessage />
                    </>
                  )}
                />
              </div>
              <div className="flex-1 space-y-1">
                <FormField
                  name="maxPaths"
                  rules={{
                    required: "Max paths is required",
                    min: { value: 1, message: "Must be ≥ 1" },
                    max: { value: 100, message: "Must be ≤ 100" },
                    valueAsNumber: true,
                  }}
                  render={({ field }) => (
                    <>
                      <FormLabel>Max Paths</FormLabel>
                      <FormInput>
                        <Input
                          type="number"
                          min={1}
                          max={100}
                          value={(field.value as number) ?? 10}
                          onChange={(e) => field.onChange(Number(e.target.value))}
                        />
                      </FormInput>
                      <FormMessage />
                    </>
                  )}
                />
              </div>
            </div>

            <FormField
              name="kindFilter"
              render={({ field }) => (
                <KindMultiSelect
                  value={(field.value as string[]) ?? []}
                  onChange={field.onChange}
                  label="Include only these kinds"
                  filter={isVisibleNamespace}
                />
              )}
            />

            <FormField
              name="excludedKinds"
              render={({ field }) => (
                <KindMultiSelect
                  value={(field.value as string[]) ?? []}
                  onChange={field.onChange}
                  label="Exclude kinds"
                  placeholder="Search kinds to exclude..."
                  showChips
                  chipTone="red"
                  filter={isVisibleNamespace}
                />
              )}
            />
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <FormSubmit isPending={isPending} className="w-full">
        Find Paths
      </FormSubmit>
    </Form>
  );
}
```

Notes for the engineer:
- The `Form` wrapper's `UseFormReturn` typing is for an untyped form record; the cast `as unknown as UseFormReturn` is the path of least resistance and matches what other Infrahub forms do (see `frontend/app/src/shared/components/form/dynamic-form.tsx`). If `pnpm tsc --noEmit` complains, compare to a working call site.
- `FormField` uses `Controller` under the hood and the `render` prop pattern. Each callback receives `{ field }` where `field.value` / `field.onChange` are typed as `unknown` due to the wrapper's looseness — the casts above match existing Infrahub conventions.
- `valueAsNumber: true` ensures RHF stores numeric values; the explicit `onChange={(e) => field.onChange(Number(...))}` provides belt-and-suspenders parsing for the controlled `Input`.

- [ ] **Step 6: Implement `path-mode-results.tsx`**

Create `frontend/app/src/entities/path-traversal/ui/path-mode/path-mode-results.tsx`:

```tsx
import { Spinner } from "@infrahub/ui";
import { useState } from "react";

import { PathFlowGraph } from "../path-flow-graph";
import {
  copyAllPathsAsText,
  formatPathAsText,
  getKindCounts,
  pathPreview,
} from "../format-paths";
import type { PathTraversalResponse } from "../../domain/get-path-traversal";

type PathModeResultsProps = {
  data: PathTraversalResponse | undefined;
  isLoading: boolean;
  error: Error | null;
  selectedPath: number;
  onSelectPath: (index: number) => void;
  onExcludeKind: (kind: string) => void;
};

export function PathModeResults({
  data,
  isLoading,
  error,
  selectedPath,
  onSelectPath,
  onExcludeKind,
}: PathModeResultsProps) {
  const [copyFeedback, setCopyFeedback] = useState("");

  async function handleCopy(text: string) {
    await navigator.clipboard.writeText(text);
    setCopyFeedback("Copied!");
    setTimeout(() => setCopyFeedback(""), 2000);
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="max-w-md rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-red-700 text-sm">{error.message}</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-500">
        <Spinner />
        <span className="text-sm">Finding paths...</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-gray-300 text-sm">
        Select two objects and click "Find Paths"
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-gray-200 border-b p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-medium text-gray-700 text-sm">
            {data.total_paths_found} path{data.total_paths_found !== 1 ? "s" : ""} found
          </h3>
          {data.paths.length > 0 && (
            <button
              type="button"
              onClick={() => handleCopy(copyAllPathsAsText(data))}
              className="rounded px-2 py-0.5 text-blue-600 text-xs hover:bg-blue-50"
              title="Copy all paths to clipboard"
            >
              {copyFeedback || "Copy all"}
            </button>
          )}
        </div>

        {data.paths.length > 0 ? (
          <div className="space-y-1">
            {data.paths.map((path, index) => (
              <div
                key={index}
                className={`group flex items-start gap-1 rounded-md border p-2 transition-colors ${
                  selectedPath === index
                    ? "border-blue-300 bg-blue-50"
                    : "border-transparent hover:border-gray-200 hover:bg-gray-50"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectPath(index)}
                  className="min-w-0 flex-1 text-left"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-medium text-xs ${
                        selectedPath === index ? "text-blue-700" : "text-gray-600"
                      }`}
                    >
                      Path {index + 1}
                    </span>
                    <span className="rounded-full bg-gray-200 px-1.5 py-0.5 text-[10px] text-gray-500">
                      {path.depth} hop{path.depth !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-gray-400">
                    {pathPreview(path)}
                  </div>
                  <div className="mt-0.5 truncate text-[10px] text-gray-300">
                    {getKindCounts(path)}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => handleCopy(formatPathAsText(data, index))}
                  className="mt-0.5 flex-shrink-0 rounded p-0.5 text-gray-300 opacity-0 transition-opacity hover:text-gray-500 group-hover:opacity-100"
                  title="Copy this path"
                >
                  copy
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-400 text-sm">No paths found</div>
        )}

        {data.paths[selectedPath] && (
          <div className="mt-3 rounded-md border border-gray-100 bg-gray-50 p-2 text-[11px] text-gray-600 leading-relaxed">
            {formatPathAsText(data, selectedPath)}
          </div>
        )}
      </div>

      {data.paths.length > 0 && (
        <div className="relative flex-1">
          <PathFlowGraph
            data={data}
            selectedPathIndex={selectedPath}
            onPathSelect={onSelectPath}
            onExcludeKind={onExcludeKind}
          />
        </div>
      )}
    </div>
  );
}
```

Note: the inline copy-icon SVG from the original page was replaced with the literal text `copy`. If you want to preserve the original SVG, copy it verbatim from `frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx:389-401` into the inner button.

- [ ] **Step 7: Implement `path-mode-panel.tsx`**

Create `frontend/app/src/entities/path-traversal/ui/path-mode/path-mode-panel.tsx`:

```tsx
import { useForm } from "react-hook-form";

import { useGetPathTraversal } from "../../domain/path-traversal.query";
import { PathModeForm } from "./path-mode-form";
import { PathModeResults } from "./path-mode-results";
import {
  formValuesToParams,
  type PathModeFormValues,
  paramsToFormValues,
  usePathModeParams,
} from "./use-path-mode-params";

export function PathModePanel() {
  const [params, setParams] = usePathModeParams();
  const formValues = paramsToFormValues(params);

  // RHF auto-resets the form when `values` deep-changes; no useEffect needed.
  const form = useForm<PathModeFormValues>({
    defaultValues: formValues,
    values: formValues,
  });

  const query = useGetPathTraversal(
    {
      sourceId: params.source,
      destinationId: params.destination,
      maxDepth: params.depth,
      maxPaths: params.maxPaths,
      kindFilter: params.kindFilter,
      excludedKinds: params.excludedKinds,
    },
    { enabled: !!params.source && !!params.destination }
  );

  return (
    <div className="flex h-full flex-col">
      <PathModeForm
        form={form}
        onSubmit={(values) => setParams(formValuesToParams(values))}
        isPending={query.isFetching}
      />
      <div className="flex-1 overflow-hidden">
        <PathModeResults
          data={query.data}
          isLoading={query.isLoading}
          error={query.error as Error | null}
          selectedPath={params.selectedPath}
          onSelectPath={(index) => setParams({ selectedPath: index })}
          onExcludeKind={(kind) =>
            setParams((prev) => ({
              excludedKinds: prev.excludedKinds.includes(kind)
                ? prev.excludedKinds
                : [...prev.excludedKinds, kind],
            }))
          }
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Run typecheck and unit tests**

Run: `cd frontend/app && pnpm tsc --noEmit && pnpm test -- --run`
Expected: green. The new files are not yet wired into the page, so behavior is unchanged.

- [ ] **Step 9: Lint and commit**

```bash
cd frontend/app && pnpm biome:fix src/entities/path-traversal/ui/path-mode/
cd /Users/paul/Projects/infrahub
git add frontend/app/src/entities/path-traversal/ui/path-mode/
git commit -m "feat(path-traversal): add path-mode panel, form, results, URL hook"
```

---

## Task 6: Dependencies-mode folder

**Files:**
- Create: `frontend/app/src/entities/path-traversal/ui/dependencies-mode/use-dependencies-mode-params.ts`
- Create: `frontend/app/src/entities/path-traversal/ui/dependencies-mode/use-dependencies-mode-params.test.ts`
- Create: `frontend/app/src/entities/path-traversal/ui/dependencies-mode/dependencies-mode-form.tsx`
- Create: `frontend/app/src/entities/path-traversal/ui/dependencies-mode/dependencies-mode-results.tsx`
- Create: `frontend/app/src/entities/path-traversal/ui/dependencies-mode/dependencies-mode-panel.tsx`

Same shape as path-mode but with the smaller form (no advanced accordion).

- [ ] **Step 1: Write the failing helper test**

Create `frontend/app/src/entities/path-traversal/ui/dependencies-mode/use-dependencies-mode-params.test.ts`:

```ts
import { describe, expect, test } from "vitest";

import { formValuesToParams, paramsToFormValues } from "./use-dependencies-mode-params";

describe("paramsToFormValues", () => {
  test("maps URL params to form values", () => {
    expect(
      paramsToFormValues({
        source: "src-id",
        targetKinds: ["InfraDevice", "InfraInterface"],
        depth: 8,
      })
    ).toEqual({
      sourceId: "src-id",
      targetKinds: ["InfraDevice", "InfraInterface"],
      maxDepth: 8,
    });
  });
});

describe("formValuesToParams", () => {
  test("maps form values to URL param updates", () => {
    expect(
      formValuesToParams({
        sourceId: "src-id",
        targetKinds: ["InfraDevice"],
        maxDepth: 3,
      })
    ).toEqual({
      source: "src-id",
      targetKinds: ["InfraDevice"],
      depth: 3,
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/app && pnpm test -- --run src/entities/path-traversal/ui/dependencies-mode/use-dependencies-mode-params.test.ts`
Expected: FAIL with `Cannot find module './use-dependencies-mode-params'`.

- [ ] **Step 3: Implement `use-dependencies-mode-params.ts`**

Create `frontend/app/src/entities/path-traversal/ui/dependencies-mode/use-dependencies-mode-params.ts`:

```ts
import {
  parseAsInteger,
  parseAsNativeArrayOf,
  parseAsString,
  useQueryStates,
} from "nuqs";

export const DEPENDENCIES_MODE_PARAMS = {
  source: parseAsString.withDefault(""),
  targetKinds: parseAsNativeArrayOf(parseAsString).withDefault([]),
  depth: parseAsInteger.withDefault(5),
} as const;

export type DependenciesModeParams = {
  source: string;
  targetKinds: string[];
  depth: number;
};

export type DependenciesModeFormValues = {
  sourceId: string;
  targetKinds: string[];
  maxDepth: number;
};

export function paramsToFormValues(p: DependenciesModeParams): DependenciesModeFormValues {
  return {
    sourceId: p.source,
    targetKinds: p.targetKinds,
    maxDepth: p.depth,
  };
}

export function formValuesToParams(
  v: DependenciesModeFormValues
): Partial<DependenciesModeParams> {
  return {
    source: v.sourceId,
    targetKinds: v.targetKinds,
    depth: v.maxDepth,
  };
}

export function useDependenciesModeParams() {
  return useQueryStates(DEPENDENCIES_MODE_PARAMS, { history: "push" });
}
```

- [ ] **Step 4: Run helper test to verify it passes**

Run: `cd frontend/app && pnpm test -- --run src/entities/path-traversal/ui/dependencies-mode/use-dependencies-mode-params.test.ts`
Expected: PASS, 2 tests.

- [ ] **Step 5: Implement `dependencies-mode-form.tsx`**

Create `frontend/app/src/entities/path-traversal/ui/dependencies-mode/dependencies-mode-form.tsx`:

```tsx
import type { UseFormReturn } from "react-hook-form";

import { KindMultiSelect } from "@/shared/components/inputs/kind-multi-select";
import {
  Form,
  FormField,
  FormInput,
  FormLabel,
  FormMessage,
  FormSubmit,
} from "@/shared/components/ui/form";
import Input from "@/shared/components/ui/input";

import { ObjectPicker } from "../object-picker";
import { isVisibleNamespace } from "../utils";
import type { DependenciesModeFormValues } from "./use-dependencies-mode-params";

type DependenciesModeFormProps = {
  form: UseFormReturn<DependenciesModeFormValues>;
  onSubmit: (values: DependenciesModeFormValues) => void;
  isPending: boolean;
};

export function DependenciesModeForm({ form, onSubmit, isPending }: DependenciesModeFormProps) {
  return (
    <Form
      form={form as unknown as UseFormReturn}
      onSubmit={(values) => onSubmit(values as DependenciesModeFormValues)}
      className="p-4"
    >
      <FormField
        name="sourceId"
        rules={{ required: "Source is required" }}
        render={({ field }) => (
          <div className="space-y-1">
            <ObjectPicker
              label="Source Object"
              value={(field.value as string) ?? ""}
              onChange={field.onChange}
            />
            <FormMessage />
          </div>
        )}
      />

      <FormField
        name="targetKinds"
        rules={{
          validate: (value: string[]) =>
            (Array.isArray(value) && value.length > 0) || "Select at least one target kind",
        }}
        render={({ field }) => (
          <div className="space-y-1">
            <KindMultiSelect
              value={(field.value as string[]) ?? []}
              onChange={field.onChange}
              label="Target kinds"
              showChips
              chipTone="blue"
              filter={isVisibleNamespace}
            />
            <FormMessage />
          </div>
        )}
      />

      <FormField
        name="maxDepth"
        rules={{
          required: "Max depth is required",
          min: { value: 1, message: "Must be ≥ 1" },
          max: { value: 20, message: "Must be ≤ 20" },
          valueAsNumber: true,
        }}
        render={({ field }) => (
          <div className="space-y-1">
            <FormLabel>Max Depth</FormLabel>
            <FormInput>
              <Input
                type="number"
                min={1}
                max={20}
                value={(field.value as number) ?? 5}
                onChange={(e) => field.onChange(Number(e.target.value))}
              />
            </FormInput>
            <FormMessage />
          </div>
        )}
      />

      <FormSubmit
        isPending={isPending}
        className="w-full bg-amber-600 hover:bg-amber-700"
      >
        Find Dependencies
      </FormSubmit>
    </Form>
  );
}
```

The amber tint matches the current submit button. If `FormSubmit` doesn't accept `className` overrides for background color (it spreads to `Button`), test in dev and adjust by adding a custom variant prop or wrapping a `Button type="submit"` directly.

- [ ] **Step 6: Implement `dependencies-mode-results.tsx`**

Create `frontend/app/src/entities/path-traversal/ui/dependencies-mode/dependencies-mode-results.tsx`:

```tsx
import { Spinner } from "@infrahub/ui";

import type { ReachableObjectsResponse } from "../../domain/get-reachable-objects";
import { PathFlowGraph } from "../path-flow-graph";
import { getKindColor } from "../utils";

type DependenciesModeResultsProps = {
  data: ReachableObjectsResponse | undefined;
  isLoading: boolean;
  error: Error | null;
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
};

export function DependenciesModeResults({
  data,
  isLoading,
  error,
  selectedIndex,
  onSelectIndex,
}: DependenciesModeResultsProps) {
  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="max-w-md rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-red-700 text-sm">{error.message}</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-500">
        <Spinner />
        <span className="text-sm">Finding dependencies...</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-gray-300 text-sm">
        Select a source object, target kinds, and click "Find Dependencies"
      </div>
    );
  }

  // PathFlowGraph requires `destination`. Use the first reachable object as a
  // synthetic destination here. This is the same fallback used by the page
  // today; review item #7 will replace it with an optional destination prop in
  // a separate PR.
  const firstObject = data.reachable_objects[0];
  const destination = firstObject
    ? {
        id: firstObject.id,
        kind: firstObject.kind,
        display_label: firstObject.display_label,
      }
    : data.source;

  return (
    <div className="flex h-full flex-col">
      <div className="border-gray-200 border-b p-4">
        <div className="mb-2 rounded-md border border-amber-200 bg-amber-50 p-2">
          <div className="font-medium text-amber-800 text-xs">
            {data.total_found} object{data.total_found !== 1 ? "s" : ""} found
          </div>
        </div>
        <div className="space-y-1">
          {data.reachable_objects.map((object, index) => (
            <button
              key={object.id}
              type="button"
              onClick={() => onSelectIndex(index)}
              className={`flex w-full items-center gap-2 rounded-md border p-2 text-left text-xs transition-colors ${
                selectedIndex === index
                  ? "border-amber-300 bg-amber-50"
                  : "border-transparent hover:border-gray-200 hover:bg-gray-50"
              }`}
            >
              <div
                className="size-2 flex-shrink-0 rounded-full"
                style={{ backgroundColor: getKindColor(object.kind) }}
              />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{object.display_label}</div>
                <div className="truncate text-[10px] text-gray-400">
                  {object.kind} · {object.depth} hop{object.depth !== 1 ? "s" : ""}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="relative flex-1">
        <PathFlowGraph
          data={{
            paths: data.paths,
            source: data.source,
            destination,
            total_paths_found: data.paths.length,
          }}
          selectedPathIndex={selectedIndex}
          onPathSelect={onSelectIndex}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Implement `dependencies-mode-panel.tsx`**

Create `frontend/app/src/entities/path-traversal/ui/dependencies-mode/dependencies-mode-panel.tsx`:

```tsx
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useGetReachableObjects } from "../../domain/reachable-objects.query";
import { DependenciesModeForm } from "./dependencies-mode-form";
import { DependenciesModeResults } from "./dependencies-mode-results";
import {
  type DependenciesModeFormValues,
  formValuesToParams,
  paramsToFormValues,
  useDependenciesModeParams,
} from "./use-dependencies-mode-params";

export function DependenciesModePanel() {
  const [params, setParams] = useDependenciesModeParams();
  const formValues = paramsToFormValues(params);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const form = useForm<DependenciesModeFormValues>({
    defaultValues: formValues,
    values: formValues,
  });

  const query = useGetReachableObjects(
    {
      sourceId: params.source,
      targetKinds: params.targetKinds,
      maxDepth: params.depth,
    },
    { enabled: !!params.source && params.targetKinds.length > 0 }
  );

  return (
    <div className="flex h-full flex-col">
      <DependenciesModeForm
        form={form}
        onSubmit={(values) => {
          setParams(formValuesToParams(values));
          setSelectedIndex(0);
        }}
        isPending={query.isFetching}
      />
      <div className="flex-1 overflow-hidden">
        <DependenciesModeResults
          data={query.data}
          isLoading={query.isLoading}
          error={query.error as Error | null}
          selectedIndex={selectedIndex}
          onSelectIndex={setSelectedIndex}
        />
      </div>
    </div>
  );
}
```

`selectedIndex` stays component-local in dependencies mode (mirroring the current page's behavior — only the path-mode `selectedPath` was URL-tracked in the original code).

- [ ] **Step 8: Run typecheck and unit tests**

Run: `cd frontend/app && pnpm tsc --noEmit && pnpm test -- --run`
Expected: green.

- [ ] **Step 9: Lint and commit**

```bash
cd frontend/app && pnpm biome:fix src/entities/path-traversal/ui/dependencies-mode/
cd /Users/paul/Projects/infrahub
git add frontend/app/src/entities/path-traversal/ui/dependencies-mode/
git commit -m "feat(path-traversal): add dependencies-mode panel, form, results, URL hook"
```

---

## Task 7: Wire panels into the page; remove old selectors

**Files:**
- Modify: `frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx`
- Delete: `frontend/app/src/entities/path-traversal/ui/object-selector.tsx`
- Delete: `frontend/app/src/entities/path-traversal/ui/dependency-selector.tsx`

This is the cutover. The page becomes ~80 lines: header, mode tabs (`useQueryState`), a slot for the active panel.

- [ ] **Step 1: Replace `path-traversal-page.tsx`**

Open `frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx` and replace the entire file with:

```tsx
import { parseAsStringEnum, useQueryState } from "nuqs";
import { useState } from "react";

import { DependenciesModePanel } from "./dependencies-mode/dependencies-mode-panel";
import { PathModePanel } from "./path-mode/path-mode-panel";

const MODES = ["path", "dependencies"] as const;
type Mode = (typeof MODES)[number];

export function PathTraversalPage() {
  const [mode, setMode] = useQueryState(
    "mode",
    parseAsStringEnum<Mode>(MODES as unknown as Mode[]).withDefault("path")
  );
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);

  return (
    <div className="flex h-full overflow-hidden">
      <div
        className={`flex-shrink-0 overflow-y-auto border-gray-200 border-r transition-all duration-300 ${
          isPanelCollapsed ? "w-3" : "w-80"
        }`}
      >
        {isPanelCollapsed ? (
          <button
            type="button"
            onClick={() => setIsPanelCollapsed(false)}
            className="flex h-full w-full items-center justify-center bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            title="Expand panel"
          >
            ›
          </button>
        ) : (
          <>
            <div className="border-gray-200 border-b p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-lg">
                    {mode === "path" ? "Path Traversal" : "Dependencies"}
                  </h2>
                  <p className="mt-1 text-gray-500 text-sm">
                    {mode === "path"
                      ? "Find paths between two objects in the graph."
                      : "Find all connected objects of specific kinds."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsPanelCollapsed(true)}
                  className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  title="Collapse panel"
                >
                  ‹
                </button>
              </div>

              <div className="mt-2 flex gap-1">
                <button
                  type="button"
                  onClick={() => setMode("path")}
                  className={`flex-1 rounded px-2 py-1 font-medium text-xs ${
                    mode === "path"
                      ? "bg-blue-100 text-blue-700"
                      : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  Path
                </button>
                <button
                  type="button"
                  onClick={() => setMode("dependencies")}
                  className={`flex-1 rounded px-2 py-1 font-medium text-xs ${
                    mode === "dependencies"
                      ? "bg-amber-100 text-amber-700"
                      : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  Dependencies
                </button>
              </div>
            </div>

            {mode === "path" ? <PathModePanel /> : <DependenciesModePanel />}
          </>
        )}
      </div>
    </div>
  );
}
```

Notes:
- The collapse-arrow SVGs from the old file have been replaced with `›` / `‹` characters. To preserve the original SVGs verbatim, copy them from the pre-cutover file.
- The mode value `"impact"` from the previous page becomes `"dependencies"` to match the user-facing tab label and the new folder name. Anyone with a deep link using `?mode=impact` will fall back to the default `"path"` because nuqs's `parseAsStringEnum` rejects unknown values. Document this in the commit message; the tab label has always read "Dependencies" so user-visible behavior is unchanged.

- [ ] **Step 2: Delete the old selectors**

```bash
cd /Users/paul/Projects/infrahub
git rm frontend/app/src/entities/path-traversal/ui/object-selector.tsx frontend/app/src/entities/path-traversal/ui/dependency-selector.tsx
```

- [ ] **Step 3: Run typecheck and unit tests**

Run: `cd frontend/app && pnpm tsc --noEmit && pnpm test -- --run`
Expected: green. If TypeScript complains about an unused import or a missing reference, the most likely cause is a stray reference to `ObjectSelector` / `DependencySelector` somewhere — grep the codebase to find it:

```bash
grep -rn "ObjectSelector\|DependencySelector" frontend/app/src
```

These should now only appear in the now-deleted files (the `git rm` should have removed them) or in changelog entries — fix any remaining references.

- [ ] **Step 4: Manual UI verification**

Start the dev server and exercise the page:

```bash
cd frontend/app && pnpm dev
```

Verify in a browser at the dev URL:
1. Page renders with "Path Traversal" header and Path/Dependencies tabs.
2. Switching tabs updates URL to `?mode=path` / `?mode=dependencies`.
3. In path mode, picking a source and destination via the combobox, then clicking "Find Paths", populates the right panel and writes URL params.
4. Pasting a UUID into the picker's combobox returns a single matching object.
5. Submitting an empty form shows `FormMessage` text under the source field ("Source is required") and does not fire the network call.
6. Visiting `/path-traversal?mode=path&source=<id>&destination=<id>&depth=5&maxPaths=10` fires the query without clicking submit.
7. Browser back/forward updates the form fields visibly.

If any verification fails, fix the issue in the affected file before committing.

- [ ] **Step 5: Lint and commit**

```bash
cd frontend/app && pnpm biome:fix src/entities/path-traversal/ui/path-traversal-page.tsx
cd /Users/paul/Projects/infrahub
git add frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx frontend/app/src/entities/path-traversal/ui/object-selector.tsx frontend/app/src/entities/path-traversal/ui/dependency-selector.tsx
git commit -m "refactor(path-traversal): split page into per-mode panels, drop legacy selectors

The mode URL value 'impact' is renamed to 'dependencies' to match the
user-facing tab label. Old deep links using ?mode=impact fall back to the
default 'path' mode."
```

---

## Task 8: Object-shaped cache key

**Files:**
- Modify: `frontend/app/src/entities/path-traversal/domain/path-traversal.query-keys.ts`
- Modify: `frontend/app/src/entities/path-traversal/domain/path-traversal.query.ts`

The current cache key spreads positional arguments into the key array. Switch to object form so additions/removals don't reshuffle indices.

- [ ] **Step 1: Update `path-traversal.query-keys.ts`**

Replace the file contents:

```ts
type ContextParams = {
  branchName: string;
  atDate: Date | string | null;
};

export type TraversalParams = ContextParams & {
  sourceId: string;
  destinationId: string;
  maxDepth?: number;
  maxPaths?: number;
  kindFilter?: string[];
  relationshipFilter?: string[];
  excludedKinds?: string[];
};

export const pathTraversalKeys = {
  all: ["path-traversal"] as const,
  allWithContext: ({ branchName, atDate }: ContextParams) =>
    [...pathTraversalKeys.all, { branchName, atDate }] as const,
  traverse: (params: TraversalParams) =>
    [...pathTraversalKeys.all, "traverse", params] as const,
};
```

The `allWithContext` helper still exists for callers that want to invalidate everything for a branch; the `traverse` key is now flat and parameterized by the full param object so React Query's structural sharing and partial invalidation both keep working.

- [ ] **Step 2: Verify `path-traversal.query.ts` still compiles**

The existing call site in `frontend/app/src/entities/path-traversal/domain/path-traversal.query.ts:27`:

```ts
queryKey: pathTraversalKeys.traverse({
  branchName: currentBranch.name,
  atDate: timeMachineDate,
  ...params,
}),
```

is unchanged — `traverse` still accepts a `TraversalParams` object. No further edits needed there.

- [ ] **Step 3: Run typecheck and tests**

Run: `cd frontend/app && pnpm tsc --noEmit && pnpm test -- --run`
Expected: green.

- [ ] **Step 4: Lint and commit**

```bash
cd frontend/app && pnpm biome:fix src/entities/path-traversal/domain/path-traversal.query-keys.ts
cd /Users/paul/Projects/infrahub
git add frontend/app/src/entities/path-traversal/domain/path-traversal.query-keys.ts
git commit -m "refactor(path-traversal): flatten cache key to object-shape"
```

---

## Task 9: E2E coverage bump

**Files:**
- Modify: `frontend/app/tests/e2e/path-traversal.spec.ts`

Bump from "static text only" to actual flows. Use the existing E2E setup (`ACCOUNT_STATE_PATH.ADMIN`) and assume the demo dataset is loaded — the existing static tests already do this. Read the existing file first to keep style consistent (it lives at `frontend/app/tests/e2e/path-traversal.spec.ts`).

- [ ] **Step 1: Add a deep-link auto-run E2E**

Open `frontend/app/tests/e2e/path-traversal.spec.ts` and append a new test inside the existing `test.describe("path-traversal", () => { ... })` block:

```ts
test("auto-runs the query when source and destination are present in the URL", async ({ page }) => {
  // Use a known seeded device id from the demo dataset (replace with real id at runtime).
  // The fixture in this repo uses /objects/InfraDevice/<id> URLs; pick the first device, copy its id.
  await page.goto("/objects/InfraDevice");
  const firstDeviceLink = page.getByRole("link").filter({ hasText: /atl1-edge|ord1-edge|jfk1-edge/ }).first();
  const sourceHref = await firstDeviceLink.getAttribute("href");
  const sourceId = sourceHref?.split("/").pop() ?? "";

  const secondDeviceLink = page.getByRole("link").filter({ hasText: /atl1-edge|ord1-edge|jfk1-edge/ }).nth(1);
  const destinationHref = await secondDeviceLink.getAttribute("href");
  const destinationId = destinationHref?.split("/").pop() ?? "";

  await page.goto(
    `/path-traversal?mode=path&source=${sourceId}&destination=${destinationId}&depth=5&maxPaths=10`
  );

  // The query should fire automatically — wait for either the "paths found" header or
  // the "No paths found" empty state.
  await expect(
    page.getByText(/path[s]? found|No paths found/i)
  ).toBeVisible({ timeout: 10_000 });
});
```

Notes:
- Replace the device-name regex with names appropriate to whatever demo dataset CI uses; the existing E2E file already references this dataset, so cross-reference its setup.
- If extracting ids from `/objects/InfraDevice` proves brittle, an alternative is to hard-code two known seeded ids if the dataset uses stable UUIDs across runs.

- [ ] **Step 2: Add a validation-feedback E2E**

In the same `test.describe` block:

```ts
test("shows validation message when submitting without a source", async ({ page }) => {
  await page.goto("/path-traversal");

  await page.getByRole("button", { name: /find paths/i }).click();

  await expect(page.getByText("Source is required")).toBeVisible();
  // The query should not have fired — the right panel still shows the empty state.
  await expect(page.getByText(/select two objects/i)).toBeVisible();
});
```

- [ ] **Step 3: Add a UUID-paste search E2E**

```ts
test("UUID pasted into the source picker resolves to a single match", async ({ page }) => {
  await page.goto("/objects/InfraDevice");
  const firstDeviceLink = page.getByRole("link").filter({ hasText: /atl1-edge|ord1-edge|jfk1-edge/ }).first();
  const href = await firstDeviceLink.getAttribute("href");
  const knownId = href?.split("/").pop() ?? "";

  await page.goto("/path-traversal");

  // Open the source picker and type the UUID.
  await page.getByRole("button", { name: /select a kind/i }).first().click();
  // The picker is the combobox below the kind dropdown; cmdk surfaces it as role="combobox".
  const search = page.getByRole("combobox").filter({ hasText: /search by name|paste an object id/i }).first();
  await search.click();
  await search.fill(knownId);

  // Exactly one result should appear — selecting it populates the chip with the resolved label.
  const result = page.getByRole("option").first();
  await expect(result).toBeVisible({ timeout: 5_000 });
  await result.click();

  // The resolved id chip is now visible under the picker.
  await expect(page.getByText(knownId)).toBeVisible();
});
```

- [ ] **Step 4: Run the E2E suite locally (if the dev server / DB are available)**

Run: `cd frontend/app && pnpm test:e2e -- path-traversal.spec.ts`

If the test environment isn't available locally, lint and run typecheck on the spec file at minimum:

```bash
cd frontend/app && pnpm biome:fix tests/e2e/path-traversal.spec.ts
cd frontend/app && pnpm tsc --noEmit
```

If the new tests fail because the demo dataset's device labels differ, adjust the regex in the test setup to match seeded names. Don't modify production code from inside this task — fix the test.

- [ ] **Step 5: Commit**

```bash
cd /Users/paul/Projects/infrahub
git add frontend/app/tests/e2e/path-traversal.spec.ts
git commit -m "test(path-traversal): cover deep-link auto-run, validation, UUID search"
```

---

## Final verification

Once all 9 tasks are done, run the full local pre-CI battery:

```bash
cd frontend/app && pnpm biome:fix
cd frontend/app && pnpm tsc --noEmit
cd frontend/app && pnpm test -- --run
cd frontend/app && pnpm test:e2e -- path-traversal.spec.ts
```

Expected: all four green.

Final manual check in a dev server:
- All seven items from Task 7 step 4 still pass.
- The dependencies mode submits, results render, and the URL contains `?mode=dependencies&source=...&targetKinds=...&depth=...`.
- Browser refresh on each form's URL shows the same state and re-runs the query.

Then squash, rebase on `develop` if needed, and open the PR.

---

## Spec coverage check

A quick map of each spec section to the task that implements it:

| Spec section | Implemented in |
|---|---|
| File layout | Tasks 3, 5, 6, 7 |
| Data flow (URL → form via `values` prop, submit → URL → query enable) | Tasks 5, 6 |
| Path mode form (fields, rules, accordion, swap) | Task 5 |
| Dependencies mode form | Task 6 |
| `RelationshipComboboxList` UUID auto-detect | Task 2 |
| `is-uuid` helper | Task 1 |
| `ObjectPicker` simplification (drop mode toggle, id-only, drop `displayLabel`) | Task 4 |
| URL state hooks (per-mode `useQueryStates`) | Tasks 5, 6 |
| Page-level mode toggle via `useQueryState` | Task 7 |
| Pure formatters extracted | Task 3 |
| Cache key shape | Task 8 |
| E2E coverage (happy path, validation, deep-link, UUID search) | Task 9 |

Out-of-scope items from the spec (review #7, #9, full #3) are not in this plan, by design.
