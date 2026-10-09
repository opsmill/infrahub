import {
  type RepositoryCommitLog,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";

export function getPendingImportCount({
  condition,
  pending_count,
}: Pick<RepositoryCommitLog, "condition" | "pending_count">): number | null {
  if (condition === RepositoryGitCondition.IN_SYNC) return 0;
  if (condition === RepositoryGitCondition.BEHIND) return pending_count;
  return null;
}
