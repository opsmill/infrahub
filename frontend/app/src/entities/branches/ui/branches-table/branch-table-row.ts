import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type { BranchRepositorySummary } from "@/entities/branches/domain/model/branch-repository-summary";

export interface BranchTableRow extends BranchListItem {
  repositorySummary: BranchRepositorySummary;
}

const PENDING_SUMMARY: BranchRepositorySummary = { status: "pending" };

export function toBranchTableRows(
  branches: readonly BranchListItem[],
  summaries: Record<string, BranchRepositorySummary>
): BranchTableRow[] {
  return branches.map((branch) => ({
    ...branch,
    repositorySummary: summaries[branch.name] ?? PENDING_SUMMARY,
  }));
}
