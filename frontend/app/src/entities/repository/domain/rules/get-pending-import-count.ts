import {
  REPOSITORY_GIT_CONDITION,
  type RepositoryCommitLog,
} from "@/entities/repository/domain/model/repository";

export function getPendingImportCount({
  condition,
  pendingCount,
}: Pick<RepositoryCommitLog, "condition" | "pendingCount">): number | null {
  if (condition === REPOSITORY_GIT_CONDITION.IN_SYNC) return 0;
  if (condition === REPOSITORY_GIT_CONDITION.BEHIND) return pendingCount;
  return null;
}
