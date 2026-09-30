import {
  REPOSITORY_GIT_CONDITION,
  type RepositoryCommitLog,
} from "@/entities/repository/domain/model/repository";

export function isGitStateAvailable({
  condition,
}: Pick<RepositoryCommitLog, "condition">): boolean {
  return condition !== REPOSITORY_GIT_CONDITION.UNAVAILABLE;
}
