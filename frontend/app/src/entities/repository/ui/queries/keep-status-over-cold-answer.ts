import { replaceEqualDeep } from "@tanstack/react-query";

import type { RepositoryCommitStatus } from "@/entities/repository/domain/model/repository";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";

export function keepStatusOverColdAnswer(
  previous: RepositoryCommitStatus | undefined,
  next: RepositoryCommitStatus
): RepositoryCommitStatus {
  return previous && isGitStateAvailable(previous) && !isGitStateAvailable(next)
    ? previous
    : replaceEqualDeep(previous, next);
}
