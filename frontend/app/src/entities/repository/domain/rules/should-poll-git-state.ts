import {
  type RepositoryCommitStatus,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";

export function shouldPollGitState({
  condition,
  unavailable,
}: Pick<RepositoryCommitStatus, "condition" | "unavailable">): boolean {
  return (
    condition === RepositoryGitCondition.UNAVAILABLE &&
    unavailable?.reason !== RepositoryGitUnavailableReason.NOT_IMPLEMENTED
  );
}
