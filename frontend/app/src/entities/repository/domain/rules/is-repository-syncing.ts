import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { REPOSITORY_SYNC_STATUS_SYNCING } from "@/entities/repository/domain/model/repository";

export function isRepositorySyncing(repository: BranchRepository): boolean {
  return repository.syncStatus.value === REPOSITORY_SYNC_STATUS_SYNCING;
}
