import type { Filter } from "@/shared/hooks/useFilters";

export interface BranchActionStateKeyParams {
  branchName: string;
  workflow: ReadonlyArray<string>;
  state: ReadonlyArray<string>;
}

export const branchesQueryKeys = {
  all: ["branches"] as const,
  list: (params: { filters?: Filter[] }) => [...branchesQueryKeys.all, "list", params] as const,
  count: (filters?: Filter[]) => [...branchesQueryKeys.all, "count", filters] as const,
  details: ({ branchName }: { branchName: string }) => [...branchesQueryKeys.all, branchName],
  actionState: (params: BranchActionStateKeyParams) =>
    [...branchesQueryKeys.all, "action-state", params] as const,
} as const;
