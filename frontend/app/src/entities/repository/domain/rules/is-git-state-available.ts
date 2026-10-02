import {
  type RepositoryCommitLog,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";

export function isGitStateAvailable({
  condition,
}: Pick<RepositoryCommitLog, "condition">): boolean {
  return condition !== RepositoryGitCondition.UNAVAILABLE;
}
