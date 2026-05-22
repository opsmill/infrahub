# Apollo → TanStack Query Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all Apollo React hook usage (`useQuery`, `useMutation`, `useLazyQuery`) from the Infrahub frontend feature code, keeping `ApolloClient` as the GraphQL transport.

**Architecture:** Migrate ~16 files in 7 sequenced PR groups. Each migration follows the established entity-layer pattern (`api/` → `domain/` → `ui/queries/`) already used by `entities/resource-manager` and other modernised features. Apollo's `ApolloProvider`, client instance, and `gql` tag literal stay untouched.

**Tech Stack:** TypeScript, React 19, TanStack Query v5, Apollo Client (kept as transport), Jotai, Vitest, Playwright, Biome.

**Companion spec:** `docs/superpowers/specs/2026-05-20-apollo-tanstack-migration-design.md`

---

## Canonical Migration Pattern (reference for all tasks)

Each migrated query produces 3–4 files following `dev/knowledge/frontend/entities-structure.md`:

```text
entities/<feature>/
  api/<verb>-<noun>-from-api.ts        # graphqlClient.query/mutate call
  domain/<verb>-<noun>.ts              # typed function, throws on error
  ui/queries/<feature>.query-keys.ts   # query key factory (one per entity, append keys)
  ui/queries/<verb>-<noun>.query.ts    # queryOptions + useGetX hook
                  OR
  ui/queries/<verb>-<noun>.mutation.ts # useMutation hook
```

**Query hook shape:**

```ts
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetXParams, getX } from "@/entities/<feature>/domain/get-x";
import { xQueryKeys } from "@/entities/<feature>/ui/queries/x.query-keys";

export function getXQueryOptions(params: GetXParams) {
  return queryOptions({
    queryKey: xQueryKeys.detail(params),
    queryFn: () => getX(params),
  });
}

export function useGetX(params: Omit<GetXParams, "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);
  return useQuery(getXQueryOptions({ branchName: currentBranch.name, atDate, ...params }));
}
```

**Mutation hook shape:**

```ts
import { useMutation } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type XParams, x } from "@/entities/<feature>/domain/x";

export function useX() {
  const { currentBranch } = useCurrentBranch();
  return useMutation({
    mutationFn: (params: Omit<XParams, "branchName">) =>
      x({ branchName: currentBranch.name, ...params }),
  });
}
```

**Polling behavior (Apollo → TanStack):**

| Apollo                          | TanStack equivalent                                                    |
|---------------------------------|------------------------------------------------------------------------|
| `pollInterval: 5000`            | `refetchInterval: 5000`                                                |
| Polls when tab hidden (default) | `refetchIntervalInBackground: true` — set when needed                  |
| `NetworkStatus.loading` (1)     | `status === "pending"`                                                 |
| `NetworkStatus.refetch` (4)     | `isRefetching === true`                                                |
| `NetworkStatus.ready` (7)       | `status === "success"`                                                 |
| `refetch()`                     | `refetch()` (same name, same semantics)                                |

**State equivalents in components:**

| Apollo property | TanStack equivalent              |
|-----------------|----------------------------------|
| `loading`       | `isPending` (or `isLoading`)     |
| `error`         | `error` / `isError`              |
| `data`          | `data`                           |
| `refetch`       | `refetch`                        |

**Naming conventions** (`dev/guidelines/frontend/naming-conventions.md`):
- All files: `kebab-case`
- API: `<verb>-<noun>-from-api.ts`
- Domain: `<verb>-<noun>.ts`
- Query/Mutation: `<verb>-<noun>.query.ts` / `<verb>-<noun>.mutation.ts`
- Query keys: `<noun>.query-keys.ts` (one factory per entity, append keys to it)
- Query-key shape: object-typed params, not positional spreads

---

## Task 0: Preflight — Baseline Capture

**Files:**
- Create: `docs/superpowers/plans/2026-05-20-apollo-tanstack-migration.baseline.md` (notes)

- [ ] **Step 1: Confirm clean working tree**

```bash
cd /Users/paul/Projects/infrahub && git status
```

Expected: working tree clean on `develop`.

- [ ] **Step 2: Run baseline tests**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm install
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run
```

Expected: all unit tests green. Record duration and pass count.

- [ ] **Step 3: Capture baseline bundle size**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm build 2>&1 | tee /tmp/baseline-build.log
```

Record gzipped size of the main app chunk(s) from the build summary.

- [ ] **Step 4: Capture baseline Apollo footprint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && rg "from ['\"]@apollo/client['\"]" src | wc -l
```

Record the count (expected ~45 import lines as of writing).

- [ ] **Step 5: Save baseline notes**

Write the gathered numbers (test pass count, bundle gzip size, Apollo import count) into `docs/superpowers/plans/2026-05-20-apollo-tanstack-migration.baseline.md`. These feed Task 23's done-criteria check.

- [ ] **Step 6: Commit baseline**

```bash
cd /Users/paul/Projects/infrahub && git add docs/superpowers/plans/2026-05-20-apollo-tanstack-migration.baseline.md docs/superpowers/specs/2026-05-20-apollo-tanstack-migration-design.md docs/superpowers/plans/2026-05-20-apollo-tanstack-migration.md
cd /Users/paul/Projects/infrahub && git commit -m "docs: add Apollo→TanStack migration spec, plan, and baseline

Records the design, implementation plan, and pre-migration baseline (bundle size,
test count, Apollo import count) so post-migration deltas are measurable."
```

---

## Group 1 — Branch Action Buttons

Three buttons (`branch-merge-button.tsx`, `branch-validate-button.tsx`, `branch-rebase-button.tsx`) all consume the same Apollo `useQuery(GET_BRANCH_ACTION_STATE, { pollInterval: 5000 })`. Merge and Validate also call `graphqlClient.mutate(...)` directly. Migration creates:

- A shared `useGetBranchActionState` hook (replaces three Apollo `useQuery` calls).
- `useMergeBranch` and `useValidateBranch` mutation hooks (replace inline `graphqlClient.mutate` in two buttons).
- Renames the misnamed `getBranchActionState.ts`, `mergeBranch.ts`, `validateBranch.ts` to kebab-case while migrating.

### Task 1: Branch query keys — extend factory

**Files:**
- Create: `frontend/app/src/entities/branches/ui/queries/branch.query-keys.ts` (if missing) or modify existing.

- [ ] **Step 1: Locate or create the key factory**

```bash
ls /Users/paul/Projects/infrahub/frontend/app/src/entities/branches/ui/queries/branch.query-keys.ts 2>/dev/null || echo "MISSING"
```

If MISSING, create it from scratch. If present, modify to add the `actionState` key.

- [ ] **Step 2: Write the factory**

```ts
// frontend/app/src/entities/branches/ui/queries/branch.query-keys.ts
export interface BranchActionStateKeyParams {
  branchName: string;
  workflow: ReadonlyArray<string>;
  state: ReadonlyArray<string>;
}

export const branchQueryKeys = {
  all: ["branches"] as const,
  actionState: (params: BranchActionStateKeyParams) =>
    [
      ...branchQueryKeys.all,
      "action-state",
      params.branchName,
      params.workflow,
      params.state,
    ] as const,
};
```

If the file already exists with other keys, merge — preserve existing keys, add `actionState`.

- [ ] **Step 3: Lint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/ui/queries/branch.query-keys.ts
```

### Task 2: Branch action-state API + domain

**Files:**
- Rename: `frontend/app/src/entities/branches/api/getBranchActionState.ts` → `get-branch-action-state-from-api.ts`
- Create: `frontend/app/src/entities/branches/domain/get-branch-action-state.ts`

- [ ] **Step 1: Move the gql constant to a kebab-case file**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && git mv src/entities/branches/api/getBranchActionState.ts src/entities/branches/api/get-branch-action-state-from-api.ts
```

- [ ] **Step 2: Convert the file to a callable fetcher**

Replace contents of `src/entities/branches/api/get-branch-action-state-from-api.ts` with:

```ts
import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_BRANCH_ACTION_STATE = graphql(`
  query GET_BRANCH_ACTION_STATE($branch: String!, $workflow: [String], $state: [StateType]) {
    InfrahubTask(branch: $branch, workflow: $workflow, state: $state) {
      count
    }
  }
`);

export interface GetBranchActionStateFromApiParams {
  branchName: string;
  workflow: ReadonlyArray<string>;
  state: ReadonlyArray<string>;
}

export function getBranchActionStateFromApi(params: GetBranchActionStateFromApiParams) {
  return graphqlClient.query({
    query: GET_BRANCH_ACTION_STATE,
    variables: {
      branch: params.branchName,
      workflow: [...params.workflow],
      state: [...params.state],
    },
    fetchPolicy: "no-cache",
  });
}
```

- [ ] **Step 3: Write the domain function**

Create `src/entities/branches/domain/get-branch-action-state.ts`:

```ts
import {
  type GetBranchActionStateFromApiParams,
  getBranchActionStateFromApi,
} from "@/entities/branches/api/get-branch-action-state-from-api";

export type GetBranchActionStateParams = GetBranchActionStateFromApiParams;

export interface BranchActionState {
  ongoingTaskCount: number;
}

export async function getBranchActionState(
  params: GetBranchActionStateParams,
): Promise<BranchActionState> {
  const { data, errors } = await getBranchActionStateFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return { ongoingTaskCount: data?.InfrahubTask?.count ?? 0 };
}
```

- [ ] **Step 4: Lint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/api/get-branch-action-state-from-api.ts src/entities/branches/domain/get-branch-action-state.ts
```

### Task 3: Branch action-state TanStack hook

**Files:**
- Create: `frontend/app/src/entities/branches/ui/queries/get-branch-action-state.query.ts`

- [ ] **Step 1: Write the query options + hook**

```ts
// frontend/app/src/entities/branches/ui/queries/get-branch-action-state.query.ts
import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  type GetBranchActionStateParams,
  getBranchActionState,
} from "@/entities/branches/domain/get-branch-action-state";
import { branchQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";

export function getBranchActionStateQueryOptions(params: GetBranchActionStateParams) {
  return queryOptions({
    queryKey: branchQueryKeys.actionState({
      branchName: params.branchName,
      workflow: params.workflow,
      state: params.state,
    }),
    queryFn: () => getBranchActionState(params),
  });
}

export interface UseGetBranchActionStateParams {
  branchName: string;
  workflow: ReadonlyArray<string>;
  state: ReadonlyArray<string>;
}

export function useGetBranchActionState(params: UseGetBranchActionStateParams) {
  return useQuery({
    ...getBranchActionStateQueryOptions(params),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}
```

Note: `refetchIntervalInBackground: true` preserves Apollo's `pollInterval` behaviour (Apollo polls when tab hidden; TanStack defaults to pausing background polling).

- [ ] **Step 2: Lint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/ui/queries/get-branch-action-state.query.ts
```

### Task 4: Test the action-state hook

**Files:**
- Create: `frontend/app/src/entities/branches/ui/queries/get-branch-action-state.query.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/app/src/entities/branches/ui/queries/get-branch-action-state.query.test.ts
import { describe, expect, it, vi } from "vitest";

import { getBranchActionStateQueryOptions } from "./get-branch-action-state.query";

vi.mock("@/entities/branches/domain/get-branch-action-state", () => ({
  getBranchActionState: vi.fn().mockResolvedValue({ ongoingTaskCount: 0 }),
}));

describe("getBranchActionStateQueryOptions", () => {
  it("builds a stable, object-form query key", () => {
    const opts = getBranchActionStateQueryOptions({
      branchName: "main",
      workflow: ["foo"],
      state: ["RUNNING"],
    });

    expect(opts.queryKey).toEqual([
      "branches",
      "action-state",
      "main",
      ["foo"],
      ["RUNNING"],
    ]);
  });
});
```

- [ ] **Step 2: Run the test**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run src/entities/branches/ui/queries/get-branch-action-state.query.test.ts
```

Expected: PASS (test asserts on key shape produced by the implementation just written).

### Task 5: Merge-branch API rename + domain

**Files:**
- Rename: `frontend/app/src/entities/branches/api/mergeBranch.ts` → `merge-branch-from-api.ts`
- Create: `frontend/app/src/entities/branches/domain/merge-branch.ts`

- [ ] **Step 1: Rename the file**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && git mv src/entities/branches/api/mergeBranch.ts src/entities/branches/api/merge-branch-from-api.ts
```

- [ ] **Step 2: Convert to a callable mutation fetcher**

Replace contents of `src/entities/branches/api/merge-branch-from-api.ts`:

```ts
import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const BRANCH_MERGE = graphql(`
  mutation BRANCH_MERGE($name: String) {
    BranchMerge(wait_until_completion: false, data: { name: $name }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface MergeBranchFromApiParams {
  branchName: string;
}

export function mergeBranchFromApi({ branchName }: MergeBranchFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCH_MERGE,
    variables: { name: branchName },
    context: { branch: branchName },
  });
}
```

- [ ] **Step 3: Write the domain function**

Create `src/entities/branches/domain/merge-branch.ts`:

```ts
import {
  type MergeBranchFromApiParams,
  mergeBranchFromApi,
} from "@/entities/branches/api/merge-branch-from-api";

export type MergeBranchParams = MergeBranchFromApiParams;

export interface MergeBranchResult {
  ok: boolean;
  taskId: string | null;
}

export async function mergeBranch(params: MergeBranchParams): Promise<MergeBranchResult> {
  const { data, errors } = await mergeBranchFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return {
    ok: data?.BranchMerge?.ok ?? false,
    taskId: data?.BranchMerge?.task?.id ?? null,
  };
}
```

- [ ] **Step 4: Lint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/api/merge-branch-from-api.ts src/entities/branches/domain/merge-branch.ts
```

### Task 6: Merge-branch mutation hook

**Files:**
- Create: `frontend/app/src/entities/branches/ui/queries/merge-branch.mutation.ts`

- [ ] **Step 1: Write the hook**

```ts
import { useMutation } from "@tanstack/react-query";

import { mergeBranch } from "@/entities/branches/domain/merge-branch";

export function useMergeBranch() {
  return useMutation({
    mutationFn: mergeBranch,
  });
}
```

- [ ] **Step 2: Lint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/ui/queries/merge-branch.mutation.ts
```

### Task 7: Validate-branch API rename + domain + mutation

**Files:**
- Rename: `frontend/app/src/entities/branches/api/validateBranch.ts` → `validate-branch-from-api.ts`
- Create: `frontend/app/src/entities/branches/domain/validate-branch.ts`
- Create: `frontend/app/src/entities/branches/ui/queries/validate-branch.mutation.ts`

- [ ] **Step 1: Rename the file**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && git mv src/entities/branches/api/validateBranch.ts src/entities/branches/api/validate-branch-from-api.ts
```

- [ ] **Step 2: Convert to a callable fetcher**

```ts
// src/entities/branches/api/validate-branch-from-api.ts
import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const BRANCH_VALIDATE = graphql(`
  mutation BRANCH_VALIDATE($name: String) {
    BranchValidate(wait_until_completion: false, data: { name: $name }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface ValidateBranchFromApiParams {
  branchName: string;
}

export function validateBranchFromApi({ branchName }: ValidateBranchFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCH_VALIDATE,
    variables: { name: branchName },
    context: { branch: branchName },
  });
}
```

- [ ] **Step 3: Write the domain function**

```ts
// src/entities/branches/domain/validate-branch.ts
import {
  type ValidateBranchFromApiParams,
  validateBranchFromApi,
} from "@/entities/branches/api/validate-branch-from-api";

export type ValidateBranchParams = ValidateBranchFromApiParams;

export interface ValidateBranchResult {
  ok: boolean;
  taskId: string | null;
}

export async function validateBranch(
  params: ValidateBranchParams,
): Promise<ValidateBranchResult> {
  const { data, errors } = await validateBranchFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return {
    ok: data?.BranchValidate?.ok ?? false,
    taskId: data?.BranchValidate?.task?.id ?? null,
  };
}
```

- [ ] **Step 4: Write the mutation hook**

```ts
// src/entities/branches/ui/queries/validate-branch.mutation.ts
import { useMutation } from "@tanstack/react-query";

import { validateBranch } from "@/entities/branches/domain/validate-branch";

export function useValidateBranch() {
  return useMutation({
    mutationFn: validateBranch,
  });
}
```

- [ ] **Step 5: Lint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/api/validate-branch-from-api.ts src/entities/branches/domain/validate-branch.ts src/entities/branches/ui/queries/validate-branch.mutation.ts
```

### Task 8: Migrate `branch-merge-button.tsx`

**Files:**
- Modify: `frontend/app/src/entities/branches/ui/branch-merge-button.tsx`

- [ ] **Step 1: Replace Apollo usage with new hooks**

Replace the file contents with:

```tsx
import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { useState } from "react";
import { toast } from "react-toastify";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { TASK_OBJECT } from "@/shared/config/constants";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useGetBranchActionState } from "@/entities/branches/ui/queries/get-branch-action-state.query";
import { useMergeBranch } from "@/entities/branches/ui/queries/merge-branch.mutation";
import { useNavigateAfterBranchRemoval } from "@/entities/branches/ui/hooks/use-navigate-after-branch-removal";
import { useConfig } from "@/entities/config/ui/config-provider";
import { BRANCH_MERGE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

type BranchMergeButtonProps = {
  branch: BranchDetail;
};

export const BranchMergeButton = ({ branch }: BranchMergeButtonProps) => {
  const { isAuthenticated } = useAuth();
  const config = useConfig();
  const { navigateToPage } = useNavigateAfterBranchRemoval();
  const [isMergeRequested, setIsMergeRequested] = useState(false);

  const {
    isPending,
    data,
    refetch,
  } = useGetBranchActionState({
    branchName: branch.name,
    workflow: [BRANCH_MERGE_WORKFLOW],
    state: TASK_ONGOING_STATES,
  });

  const mergeMutation = useMergeBranch();

  const hasOngoingTask = (data?.ongoingTaskCount ?? 0) > 0;

  const isDisabled =
    !isAuthenticated ||
    isPending ||
    !!branch.is_default ||
    branch.status === BranchStatus.MERGED ||
    isMergeRequested ||
    hasOngoingTask;

  const handleSubmit = async () => {
    setIsMergeRequested(true);

    try {
      await mergeMutation.mutateAsync({ branchName: branch.name });

      const deleteBranchAfterMerge = config.main.delete_branch_after_merge;

      const message = deleteBranchAfterMerge
        ? `Branch merge requested! Branch '${branch.name}' will be automatically deleted.`
        : "Branch merge requested!";

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />, {
        toastId: "alert-success",
      });

      if (deleteBranchAfterMerge) {
        navigateToPage("/branches", branch.name);
      }

      await refetch();
    } catch (error) {
      console.error(error);
      setIsMergeRequested(false);
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="An error occurred while merging the branch" />,
      );
    }
  };

  return (
    <Button
      isDisabled={isDisabled}
      onPress={handleSubmit}
      variant="active"
      className="flex items-center gap-2"
    >
      Merge
      <Icon icon="mdi:check" />
    </Button>
  );
};
```

Note: `TASK_OBJECT` import retained only if still referenced — search the file after edits and drop unused imports. The new `data.ongoingTaskCount` replaces `data?.[TASK_OBJECT]?.count`.

- [ ] **Step 2: Drop unused imports**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/ui/branch-merge-button.tsx
```

- [ ] **Step 3: Verify type-check + tests**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run src/entities/branches
```

Expected: existing branch tests pass; no TypeScript errors surfaced via the test compile.

### Task 9: Migrate `branch-validate-button.tsx`

**Files:**
- Modify: `frontend/app/src/entities/branches/ui/branch-validate-button.tsx`

- [ ] **Step 1: Replace Apollo usage**

```tsx
import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { toast } from "react-toastify";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useGetBranchActionState } from "@/entities/branches/ui/queries/get-branch-action-state.query";
import { useValidateBranch } from "@/entities/branches/ui/queries/validate-branch.mutation";
import { BRANCH_VALIDATE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

type BranchValidateButtonProps = {
  branch: BranchDetail;
};

export const BranchValidateButton = ({ branch }: BranchValidateButtonProps) => {
  const { isAuthenticated } = useAuth();

  const { isPending, data } = useGetBranchActionState({
    branchName: branch.name,
    workflow: [BRANCH_VALIDATE_WORKFLOW],
    state: TASK_ONGOING_STATES,
  });

  const validateMutation = useValidateBranch();

  const hasOngoingTask = (data?.ongoingTaskCount ?? 0) > 0;
  const isDisabled =
    !isAuthenticated ||
    isPending ||
    !!branch.is_default ||
    branch.status === BranchStatus.MERGED ||
    hasOngoingTask;

  const handleSubmit = async () => {
    try {
      await validateMutation.mutateAsync({ branchName: branch.name });
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Branch validation requested!" />, {
        toastId: "alert-success",
      });
    } catch (error) {
      console.error(error);
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message="An error occurred while validating the branch"
        />,
      );
    }
  };

  return (
    <Button
      isDisabled={isDisabled}
      onPress={handleSubmit}
      variant="warning"
      className="flex items-center gap-2"
    >
      Validate
      <Icon icon="mdi:shield-check-outline" />
    </Button>
  );
};
```

- [ ] **Step 2: Lint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/ui/branch-validate-button.tsx
```

### Task 10: Migrate `branch-rebase-button.tsx`

**Files:**
- Modify: `frontend/app/src/entities/branches/ui/branch-rebase-button.tsx`

- [ ] **Step 1: Replace the Apollo polling useQuery**

```tsx
import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { toast } from "react-toastify";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useGetBranchActionState } from "@/entities/branches/ui/queries/get-branch-action-state.query";
import { useRebaseBranch } from "@/entities/branches/ui/queries/rebase-branch.mutation";
import { BRANCH_REBASE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/constants";

type BranchRebaseButtonProps = {
  branch: BranchDetail;
};

export const BranchRebaseButton = ({ branch }: BranchRebaseButtonProps) => {
  const { isAuthenticated } = useAuth();
  const rebaseBranchMutation = useRebaseBranch();

  const { isPending, data, refetch } = useGetBranchActionState({
    branchName: branch.name,
    workflow: [BRANCH_REBASE_WORKFLOW],
    state: TASK_ONGOING_STATES,
  });

  const hasOngoingTask = (data?.ongoingTaskCount ?? 0) > 0;
  const isDisabled =
    !isAuthenticated ||
    isPending ||
    !!branch.is_default ||
    branch.status === BranchStatus.MERGED ||
    hasOngoingTask;

  const handleRebase = () => {
    rebaseBranchMutation.mutate(
      {
        branchName: branch.name,
        waitUntilCompletion: false,
      },
      {
        onSuccess: async () => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Branch rebase requested!" />, {
            toastId: "alert-success",
          });
          await refetch();
        },
        onError: (error) => {
          console.error("Error while rebasing branch: ", error);
          toast(
            <Alert
              type={ALERT_TYPES.ERROR}
              message="An error occurred while rebasing the branch"
            />,
          );
        },
      },
    );
  };

  return (
    <Button
      isDisabled={isDisabled}
      onPress={handleRebase}
      variant="outline"
      className="flex items-center gap-2"
    >
      Rebase
      <Icon icon="mdi:counterclockwise-arrows" />
    </Button>
  );
};
```

- [ ] **Step 2: Lint**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/branches/ui/branch-rebase-button.tsx
```

### Task 11: Verify Group 1 + commit

- [ ] **Step 1: Confirm no Apollo hook imports remain in this group**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && rg "from ['\"]@apollo/client['\"]" src/entities/branches/ui/branch-merge-button.tsx src/entities/branches/ui/branch-validate-button.tsx src/entities/branches/ui/branch-rebase-button.tsx
```

Expected: zero matches.

- [ ] **Step 2: Run branch tests + type-check**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run
cd /Users/paul/Projects/infrahub/frontend/app && pnpm build
```

Expected: tests green, build succeeds.

- [ ] **Step 3: Manually verify in dev server**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm dev
```

Smoke test in browser:
- Open a non-default branch detail page.
- Confirm Merge / Validate / Rebase buttons all disable while a workflow is running (poll behaviour).
- Trigger each action; confirm success toast appears.
- Leave the tab in the background for ~10s while a task is running, then return: poll should still reflect current state (validates `refetchIntervalInBackground: true`).

- [ ] **Step 4: Commit**

```bash
cd /Users/paul/Projects/infrahub && git add -A
cd /Users/paul/Projects/infrahub && git commit -m "refactor(frontend): migrate branch action buttons to TanStack Query

Replaces Apollo useQuery(GET_BRANCH_ACTION_STATE, { pollInterval }) and
inline graphqlClient.mutate calls in branch-{merge,validate,rebase}-button
with a shared useGetBranchActionState hook plus useMergeBranch /
useValidateBranch mutation hooks. Renames misnamed api files to
kebab-case. Apollo client is unchanged."
```

---

## Group 2 — Diff Readers

Four files use Apollo `useQuery` for read-only diff data:

- `src/entities/diff/ui/node-diff/comments.tsx`
- `src/entities/diff/ui/node-diff/thread.tsx`
- `src/entities/diff/ui/artifact-diff/artifact-content-diff.tsx`
- `src/entities/diff/ui/file-diff/file-content-diff.tsx`

### Task 12: Migrate node-diff comments + thread

**Files:**
- Read first: both files to identify the query, its variables, and any polling.
- Create: `entities/diff/api/get-<noun>-from-api.ts`, `entities/diff/domain/get-<noun>.ts`, `entities/diff/ui/queries/get-<noun>.query.ts`, and append keys to `entities/diff/ui/queries/diff.query-keys.ts` (create if absent).
- Modify: both component files to call the new `useGetX` hook.

- [ ] **Step 1: Read sources**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && cat src/entities/diff/ui/node-diff/comments.tsx src/entities/diff/ui/node-diff/thread.tsx
```

Identify: the imported gql query constant, its variables, any pollInterval, any inline transformations of the response.

- [ ] **Step 2: Build api → domain → query layers**

Follow the pattern from Group 1, Tasks 2–4. Naming: pick `verb-noun` reflecting what the query returns (e.g. `get-diff-thread.query.ts`). If the existing gql constant lives in a misnamed file, rename to kebab-case in the same task.

- [ ] **Step 3: Write a query-options unit test**

Mirror Task 4: assert the query-key shape and that the options pass through params.

- [ ] **Step 4: Replace `useQuery` callsite in each component**

Swap `const { loading, data, error } = useQuery(QUERY, { variables: ... })` for `const { isPending, data, error } = useGetX({ ... })`. Map any other Apollo properties via the equivalences table in the pattern reference.

- [ ] **Step 5: Lint + test**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/diff
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run src/entities/diff
```

### Task 13: Migrate artifact-content-diff + file-content-diff

**Files:** `artifact-content-diff.tsx`, `file-content-diff.tsx` and the api/domain/query files they require.

- [ ] **Step 1: Read sources, identify queries**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && cat src/entities/diff/ui/artifact-diff/artifact-content-diff.tsx src/entities/diff/ui/file-diff/file-content-diff.tsx
```

- [ ] **Step 2: Build api/domain/query layers** following Group 1 pattern.

- [ ] **Step 3: Write the unit test for each new query-options factory.**

- [ ] **Step 4: Replace `useQuery` callsites.**

- [ ] **Step 5: Lint + test.**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/diff
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run src/entities/diff
```

### Task 14: Group 2 verification + commit

- [ ] **Step 1: Confirm no Apollo hook imports remain in diff/ui**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && rg "from ['\"]@apollo/client['\"]" src/entities/diff/ui
```

Expected: zero matches.

- [ ] **Step 2: Smoke test in dev server**

Open a proposed change with a non-trivial diff (artifact + file + comments + thread). Confirm all four panels render with no console errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/paul/Projects/infrahub && git add -A
cd /Users/paul/Projects/infrahub && git commit -m "refactor(frontend): migrate diff readers to TanStack Query

Replaces Apollo useQuery in node-diff/comments, node-diff/thread,
artifact-content-diff, and file-content-diff with entity-layer
TanStack hooks. Read-only paths; no behavioural change."
```

---

## Group 3 — Shared Form Inputs

> **Note (post-implementation):** The initial file list below was stale by the time this group was executed — `id.tsx`, `generic-selector.tsx`, and `relationship-one.tsx` had already been migrated in earlier work. The actual remaining wrapper consumers folded into this PR are:
> - `src/shared/components/inputs/dropdown.tsx` (+ `src/entities/schema/{api,domain,ui/queries}/add-dropdown`, `remove-dropdown`)
> - `src/shared/components/inputs/enum.tsx` (+ `src/entities/schema/{api,domain,ui/queries}/add-enum`, `remove-enum`)
> - `src/entities/tasks/ui/task-display.tsx`, `task-item-details.tsx`, `src/pages/tasks/task-details.tsx` (+ `src/entities/tasks/{api,domain,ui/queries}/get-task-details`, `get-task-details-title`)
> - `src/entities/diff/ui/checks/validator-details.tsx` (+ `src/entities/diff/{api,domain,ui/queries}/get-validator-details`)
> - `src/entities/user-profile/ui/tab-update-password.tsx` (+ `src/entities/user-profile/{api,domain,ui/queries}/update-account-password`)
>
> After these migrations, `src/shared/api/graphql/useQuery` has no remaining consumers and Group 7 can delete it.

Three components in `shared/` use Apollo hooks. They are imported across many pages, so this group goes after the buttons + diffs prove the pattern.

- `src/shared/components/ui/id.tsx`
- `src/shared/components/form/generic-selector.tsx`
- `src/shared/components/inputs/relationship-one.tsx`

Shared components by convention should not own entity queries. Each one currently calls a query that belongs to a specific entity (likely `nodes/object` or `nodes/relationships`). The migration moves the query into the right entity and the shared component consumes the hook.

### Task 15: Migrate `id.tsx`

**Files:**
- Read first: `src/shared/components/ui/id.tsx`.
- Identify: which entity the query targets. Likely `nodes/object` (single-node read by UUID — the spec notes `useGetObject` already exists for this).
- Modify: replace inline `gql` + `useQuery` with `useGetObject(...)` (or equivalent existing entity hook) if applicable. If a new hook is needed, add it to the appropriate entity following the pattern.

- [ ] **Step 1: Read source**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && cat src/shared/components/ui/id.tsx
```

- [ ] **Step 2: Check existing entity hooks**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && ls src/entities/nodes/object/ui/queries/
```

If `useGetObject` already covers the case, just swap. Otherwise add a new entity hook following the Group 1 pattern.

- [ ] **Step 3: Replace the call, update the component to use the new state shape.**

- [ ] **Step 4: Lint + test.**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/shared/components/ui/id.tsx
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run
```

### Task 16: Migrate `generic-selector.tsx`

**Files:**
- Read first: `src/shared/components/form/generic-selector.tsx`.

- [ ] **Step 1: Read source.**
- [ ] **Step 2: Identify the entity owner of the query (likely `nodes/object` or `schema`).**
- [ ] **Step 3: Use existing entity hook OR add one following the pattern.**
- [ ] **Step 4: Replace the call.**
- [ ] **Step 5: Lint + test.**

### Task 17: Migrate `relationship-one.tsx`

**Files:**
- Read first: `src/shared/components/inputs/relationship-one.tsx`.

- [ ] **Step 1: Read source.**
- [ ] **Step 2: Likely consumer of `nodes/relationships` queries — check `src/entities/nodes/relationships/ui/queries/` for existing hooks.**
- [ ] **Step 3: Replace the call.**
- [ ] **Step 4: Lint + test.**

### Task 18: Group 3 verification + commit

- [ ] **Step 1: Confirm no Apollo hook imports remain in `shared/components/`**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && rg "from ['\"]@apollo/client['\"]" src/shared/components | rg -v "gql" || echo OK
```

Expected: OK (only `gql` imports left, if any).

- [ ] **Step 2: Smoke test object create/edit forms** — these shared inputs power most forms. Test:
  - Create a node via the object create form.
  - Edit a relationship via the relationship-one input.
  - The `id.tsx` indicator renders correctly on existing object detail pages.

- [ ] **Step 3: Commit**

```bash
cd /Users/paul/Projects/infrahub && git add -A
cd /Users/paul/Projects/infrahub && git commit -m "refactor(frontend): migrate shared form inputs to TanStack Query

Replaces Apollo useQuery in id.tsx, generic-selector.tsx, and
relationship-one.tsx with entity-layer TanStack hooks. Shared
components no longer reach into Apollo directly."
```

---

## Group 4 — Proposed Changes

- `src/pages/proposed-changes/new.tsx`
- `src/entities/proposed-changes/ui/proposed-change-edit-trigger.tsx`
- `src/entities/proposed-changes/ui/conversations/thread.tsx`

### Task 19: Migrate the three files

**Files:**
- Read each file first.
- Create: api/domain/query layers under `entities/proposed-changes/` as needed. Use existing files if they already exist; append new keys to `entities/proposed-changes/ui/queries/proposed-changes.query-keys.ts`.

- [ ] **Step 1: Read all three sources.**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && cat src/pages/proposed-changes/new.tsx src/entities/proposed-changes/ui/proposed-change-edit-trigger.tsx src/entities/proposed-changes/ui/conversations/thread.tsx
```

- [ ] **Step 2: For each file, build the api/domain/query layers per the Group 1 pattern.** Reuse existing layers when the query already has an entity-layer counterpart.

- [ ] **Step 3: Write a query-options test per new factory.**

- [ ] **Step 4: Replace each `useQuery` / `useMutation` callsite.** Map `loading → isPending`, `error → error`, etc.

- [ ] **Step 5: Lint + test.**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/proposed-changes src/pages/proposed-changes
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run src/entities/proposed-changes
```

- [ ] **Step 6: Smoke test:** create a proposed change, edit it, add a conversation comment. All flows green.

- [ ] **Step 7: Commit**

```bash
cd /Users/paul/Projects/infrahub && git add -A
cd /Users/paul/Projects/infrahub && git commit -m "refactor(frontend): migrate proposed-changes pages to TanStack Query

Migrates new-pc page, edit-trigger, and conversations thread off
Apollo hooks onto entity-layer TanStack hooks."
```

---

## Group 5 — Object Item Edit

- `src/entities/nodes/object-item-edit/object-item-edit-paginated.tsx`
- `src/entities/nodes/object/ui/queries/delete-objects.mutation.ts` (despite the `.mutation.ts` suffix, this file still uses Apollo — needs migration)

### Task 20: Migrate object item edit + delete-objects mutation

**Files:**
- Read first: both files.
- Modify: replace Apollo `useQuery`/`useMutation` with entity-layer TanStack hooks. The `delete-objects.mutation.ts` likely needs to switch from `useApolloMutation(MUTATION, { context })` to `useMutation({ mutationFn: ... })` plus an api/domain pair.

- [ ] **Step 1: Read sources.**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && cat src/entities/nodes/object-item-edit/object-item-edit-paginated.tsx src/entities/nodes/object/ui/queries/delete-objects.mutation.ts
```

- [ ] **Step 2: For `delete-objects.mutation.ts`** — rewrite to TanStack shape per the mutation pattern in the reference. Add an api/domain pair if missing.

- [ ] **Step 3: For `object-item-edit-paginated.tsx`** — note: this is the file that depends most heavily on the shared wrapper's auto `usePagination()` injection. After migration, pagination must be passed explicitly to the new `useGetX` hook. Lift `usePagination()` call into this component.

- [ ] **Step 4: Test + lint + smoke test the object edit/list paginated flow.**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm biome:fix src/entities/nodes/object-item-edit src/entities/nodes/object
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run src/entities/nodes
```

Smoke test: open a paginated object list, change page, edit one item, delete one or many items.

- [ ] **Step 5: Commit**

```bash
cd /Users/paul/Projects/infrahub && git add -A
cd /Users/paul/Projects/infrahub && git commit -m "refactor(frontend): migrate object item edit and delete-objects to TanStack Query

Pagination is now passed explicitly from the component instead of
being auto-injected by the shared Apollo useQuery wrapper."
```

---

## Group 6 — Tests Using Apollo `NetworkStatus`

- `src/entities/tasks/ui/task-status.test.tsx`
- `src/entities/tasks/domain/is-task-running-on-branch/is-task-running-on-branch.test.ts`

### Task 21: Replace `NetworkStatus` assertions

**Files:**
- Modify: both test files.

- [ ] **Step 1: Read both files**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && cat src/entities/tasks/ui/task-status.test.tsx src/entities/tasks/domain/is-task-running-on-branch/is-task-running-on-branch.test.ts
```

Identify every `NetworkStatus.X` usage and what state it represents.

- [ ] **Step 2: Replace `NetworkStatus.loading` (1) with TanStack `{ status: "pending", fetchStatus: "fetching" }` shape, `NetworkStatus.ready` (7) with `{ status: "success", fetchStatus: "idle" }`, `NetworkStatus.refetch` (4) with `{ status: "success", isRefetching: true }`.** The exact replacement depends on what the function/component being tested actually consumes from the query result.

- [ ] **Step 3: Drop the `@apollo/client` import.**

- [ ] **Step 4: Run tests**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run src/entities/tasks
```

Expected: tests green with new fixtures.

- [ ] **Step 5: Commit**

```bash
cd /Users/paul/Projects/infrahub && git add -A
cd /Users/paul/Projects/infrahub && git commit -m "test(frontend): replace Apollo NetworkStatus with TanStack status fields

The functions under test were always running against query-result
shapes that came from the migrated TanStack hooks, but the tests
still imported Apollo's NetworkStatus enum to build fixtures."
```

---

## Group 7 — Wrapper Removal & Cleanup

### Task 22: Delete the shared Apollo wrapper

**Files:**
- Delete: `frontend/app/src/shared/api/graphql/useQuery.ts`

- [ ] **Step 1: Confirm no remaining consumers**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && rg "shared/api/graphql/useQuery" src
```

Expected: zero matches. If any remain, return to Groups 1–5 and finish those migrations first.

- [ ] **Step 2: Delete the file**

```bash
cd /Users/paul/Projects/infrahub && git rm frontend/app/src/shared/api/graphql/useQuery.ts
```

- [ ] **Step 3: Type-check + build**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm build
```

Expected: build succeeds.

### Task 23: Final audit + bundle delta + docs

**Files:**
- Modify: `dev/knowledge/frontend/entities-structure.md` and any guideline still referencing Apollo hooks as a valid pattern.

- [ ] **Step 1: Final Apollo audit**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && rg "from ['\"]@apollo/client['\"]" src
```

Expected: only the kept set — `ApolloProvider` (app.tsx), `ApolloClient/InMemoryCache/from/link` (graphqlClientApollo.tsx), and `gql` tag imports in `entities/*/api/`. **No `useQuery`/`useMutation`/`useLazyQuery`/`useReactiveVar`/`useSubscription` imports anywhere.**

- [ ] **Step 2: Bundle delta**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm build 2>&1 | tee /tmp/post-migration-build.log
```

Diff the gzipped main-chunk size against the baseline captured in Task 0 Step 3. Target: ~40 KB reduction. Record actual delta in the commit message.

- [ ] **Step 3: Full test pass**

```bash
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test --run
cd /Users/paul/Projects/infrahub/frontend/app && pnpm test:e2e
```

Expected: unit tests green; E2E green.

- [ ] **Step 4: Update knowledge docs**

In `dev/knowledge/frontend/entities-structure.md`, ensure the wording says TanStack Query is the single server-state pattern. Add a short note: "Apollo Client is kept as the GraphQL transport (auth links, error handling) only. No Apollo React hooks are used in feature code."

Grep for any other doc still recommending Apollo hooks:

```bash
cd /Users/paul/Projects/infrahub && rg -i "apollo.*useQuery|useQuery.*apollo" dev/
```

Update or remove any stale guidance found.

- [ ] **Step 5: Commit cleanup**

```bash
cd /Users/paul/Projects/infrahub && git add -A
cd /Users/paul/Projects/infrahub && git commit -m "chore(frontend): finish Apollo→TanStack Query migration

Deletes the shared Apollo useQuery/useMutation wrapper, updates
knowledge docs to mark TanStack Query as the sole server-state
pattern, and records bundle delta of <X>KB gzip vs. baseline."
```

---

## Self-Review (against the spec)

- **Spec scope item 1: Remove all Apollo React hook usage from `src/`.** Covered by Groups 1–6 (16 files) + Task 22 (wrapper deletion).
- **Spec scope item 2: Delete `src/shared/api/graphql/useQuery.ts`.** Task 22.
- **Spec scope item 3: Preserve product behaviour — pagination, polling, branch-aware data, time-machine.** Task 3 sets `refetchIntervalInBackground: true`; Task 20 makes pagination explicit; the canonical hook pattern injects branch + datetime context.
- **Spec scope item 4: Update knowledge docs.** Task 23 Step 4.
- **Spec sequencing 1–7.** Tasks map 1:1 to spec groups (preflight + 7 groups + cleanup).
- **Risk: polling tab-hidden behaviour.** Covered by `refetchIntervalInBackground: true` in Task 3 and by manual smoke-test in Task 11 Step 3.
- **Risk: implicit pagination injection removed.** Explicit in Task 20 Step 3.
- **Risk: shared inputs touched everywhere.** Group 3 deliberately runs after Groups 1–2; smoke test in Task 18 Step 2.
- **Done criteria — zero hook imports.** Verified Task 23 Step 1.
- **Done criteria — bundle delta.** Verified Task 23 Step 2 (baseline captured Task 0).
- **Done criteria — full test pass.** Verified Task 23 Step 3.

No placeholder phrases (TBD/TODO/etc.) detected. Method signatures consistent: `useGetBranchActionState({ branchName, workflow, state })` used identically across Tasks 8, 9, 10. `mergeBranch.taskId` / `validateBranch.taskId` consistent. `branchQueryKeys.actionState` consistent across Tasks 1 and 4.
