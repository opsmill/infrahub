import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type {
  BranchRepositoriesFetch,
  BranchTableRepository,
  BranchTableRow,
} from "@/entities/branches/domain/model/branch-table-row";

type OrderRepositories = (repositories: BranchTableRepository[]) => BranchTableRepository[];

function toRowsForBranch(
  branch: BranchListItem,
  fetch: BranchRepositoriesFetch,
  orderRepositories: OrderRepositories
): BranchTableRow[] {
  const id = branch.id;

  if (fetch.status === "pending") return [{ id, branch, state: "pending", repository: null }];
  if (fetch.status === "denied") return [{ id, branch, state: "denied", repository: null }];
  if (fetch.status === "error") {
    return [{ id, branch, state: "error", repository: null, errorMessage: fetch.message }];
  }
  if (fetch.repositories.length === 0) return [{ id, branch, state: "empty", repository: null }];

  return orderRepositories(fetch.repositories).map((repository, index) => ({
    id: index === 0 ? id : `${id}:${repository.id}`,
    branch,
    state: "ok",
    repository,
  }));
}

export function toBranchTableRows({
  branches,
  fetchByBranchId,
  orderRepositories,
}: {
  branches: BranchListItem[];
  fetchByBranchId: ReadonlyMap<string, BranchRepositoriesFetch>;
  orderRepositories: OrderRepositories;
}): BranchTableRow[] {
  return branches.flatMap((branch) =>
    toRowsForBranch(
      branch,
      fetchByBranchId.get(branch.id) ?? { status: "pending" },
      orderRepositories
    )
  );
}
