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

function toFetch(result: BranchRepositoriesQueryResult | undefined): BranchRepositoriesFetch {
  if (result?.data) return result.data;
  if (result?.isError) return { status: "error", message: result.error.message };
  return { status: "pending" };
}

// Keyed by branch id so TanStack's structural sharing pairs rows by branch rather than by array
// index; otherwise every row below a branch that grows from pending to N would be a new object.
function groupByBranchId(rows: BranchTableRow[]): Record<string, BranchTableRow[]> {
  const grouped: Record<string, BranchTableRow[]> = {};
  for (const row of rows) {
    (grouped[row.branch.id] ??= []).push(row);
  }
  return grouped;
}

export function useBranchTableRows(branches: BranchListItem[]): BranchTableRow[] {
  const rowsByBranchId = useQueries({
    queries: branches.map((branch) =>
      getBranchRepositoriesQueryOptions({
        branchName: branch.name,
        syncWithGit: Boolean(branch.sync_with_git),
      })
    ),
    combine: (results) => {
      const fetchByBranchId = new Map(
        branches.map((branch, index) => [branch.id, toFetch(results[index])])
      );
      const rows = toBranchTableRows({
        branches,
        fetchByBranchId,
        orderRepositories: rankRepositories,
      });
      return groupByBranchId(rows);
    },
  });

  return branches.flatMap((branch) => rowsByBranchId[branch.id] ?? []);
}
