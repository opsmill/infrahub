import type { components } from "@/shared/api/rest/types.generated";

import type { BranchGitSyncStatus } from "@/entities/branch-git-status/domain/model/branch-git-status";
import { REPOSITORY_SYNC_STATUS_UNKNOWN } from "@/entities/repository/domain/model/repository";

type DropdownChoice = components["schemas"]["DropdownChoiceRead"];

export function getUnknownSyncStatus(
  choices: readonly DropdownChoice[] | null | undefined
): BranchGitSyncStatus {
  const choice = choices?.find(({ name }) => name === REPOSITORY_SYNC_STATUS_UNKNOWN);

  return {
    value: REPOSITORY_SYNC_STATUS_UNKNOWN,
    label: choice?.label ?? null,
    color: choice?.color ?? null,
    description: choice?.description ?? null,
  };
}
