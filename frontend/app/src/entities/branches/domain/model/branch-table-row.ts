import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type {
  BranchRepositoriesResult,
  BranchRepository,
} from "@/entities/repository/domain/model/branch-repository";

export type BranchRepositoriesFetch =
  | BranchRepositoriesResult
  | { status: "pending" }
  | { status: "error"; message: string };

type BranchTableRowState = "pending" | "ok" | "empty" | "denied" | "error";

export type BranchTableRow = { id: string; branch: BranchListItem } & (
  | { state: "ok"; repository: BranchRepository }
  | { state: "error"; repository: null; errorMessage: string }
  | { state: Exclude<BranchTableRowState, "ok" | "error">; repository: null }
);

export type BranchTableRepository = Extract<BranchTableRow, { state: "ok" }>["repository"];

export function isBranchAnchorRow(row: BranchTableRow): boolean {
  return row.id === row.branch.id;
}
