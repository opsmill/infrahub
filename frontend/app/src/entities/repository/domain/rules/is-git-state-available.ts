import {
  REPOSITORY_GIT_CONDITION,
  type RepositoryGitCondition,
  type RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";

export interface GitStateInput {
  condition: RepositoryGitCondition;
  unavailable: { reason: RepositoryGitUnavailableReason } | null;
}

export function isGitStateAvailable({ condition }: GitStateInput): boolean {
  return condition !== REPOSITORY_GIT_CONDITION.UNAVAILABLE;
}
