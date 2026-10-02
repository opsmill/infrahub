import type { BranchRepositoryHealth } from "@/entities/repository/domain/model/branch-repository";

export function isAnyRepositorySyncing(health: BranchRepositoryHealth | undefined): boolean {
  return (health?.syncingCount ?? 0) > 0;
}
