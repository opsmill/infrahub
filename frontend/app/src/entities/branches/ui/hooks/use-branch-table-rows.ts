import { type UseQueryResult, useQueries } from "@tanstack/react-query";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type {
  BranchRepositoriesFetch,
  BranchTableRow,
} from "@/entities/branches/domain/model/branch-table-row";
import { toBranchTableRows } from "@/entities/branches/domain/rules/to-branch-table-rows";
import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { rankRepositories } from "@/entities/repository/domain/rules/rank-repositories";
import { getBranchRepositoriesQueryOptions } from "@/entities/repository/ui/queries/get-branch-repositories.query";

type BranchRepositoriesQueryResult = UseQueryResult<BranchRepositoriesResult, Error>;

const PENDING_FETCH: BranchRepositoriesFetch = { status: "pending" };

// Module-level identity caches keep one branch's rows as the same objects while its
// query result is unchanged, so resolving another branch does not re-render them (SC-007).
const errorFetchByError = new WeakMap<Error, BranchRepositoriesFetch>();
const rowsByBranch = new WeakMap<
  BranchListItem,
  WeakMap<BranchRepositoriesFetch, BranchTableRow[]>
>();

function toFetch(result: BranchRepositoriesQueryResult): BranchRepositoriesFetch {
  if (result.data) return result.data;
  if (!result.isError) return PENDING_FETCH;

  const cached = errorFetchByError.get(result.error);
  if (cached) return cached;
  const fetch: BranchRepositoriesFetch = { status: "error", message: result.error.message };
  errorFetchByError.set(result.error, fetch);
  return fetch;
}

function getBranchRows(branch: BranchListItem, fetch: BranchRepositoriesFetch): BranchTableRow[] {
  const rowsByFetch = rowsByBranch.get(branch) ?? new WeakMap();
  rowsByBranch.set(branch, rowsByFetch);

  const cached = rowsByFetch.get(fetch);
  if (cached) return cached;
  const rows = toBranchTableRows({
    branches: [branch],
    fetchByBranchId: new Map([[branch.id, fetch]]),
    orderRepositories: rankRepositories,
  });
  rowsByFetch.set(fetch, rows);
  return rows;
}

export function useBranchTableRows(branches: BranchListItem[]): BranchTableRow[] {
  return useQueries({
    queries: branches.map((branch) =>
      getBranchRepositoriesQueryOptions({
        branchName: branch.name,
        syncWithGit: Boolean(branch.sync_with_git),
      })
    ),
    combine: (results) =>
      branches.flatMap((branch, index) => {
        const result = results[index];
        return getBranchRows(branch, result ? toFetch(result) : PENDING_FETCH);
      }),
  });
}
