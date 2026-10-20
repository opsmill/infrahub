import type { RepositoryRunBranchOutcome } from "@/entities/repository/domain/model/repository-activity";

export interface BranchOutcomeCounts {
  changed: number;
  failed: number;
}

/** An outcome added to the API after this was written counts as neither. */
export function countBranchOutcomes(branches: RepositoryRunBranchOutcome[]): BranchOutcomeCounts {
  return {
    changed: branches.filter(({ outcome }) => outcome === "IMPORTED").length,
    failed: branches.filter(({ outcome }) => outcome === "FAILED").length,
  };
}
