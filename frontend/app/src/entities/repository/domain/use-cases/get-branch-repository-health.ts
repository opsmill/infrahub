import type { BranchContextParams } from "@/shared/api/types";

import { toBranchRepositories } from "@/entities/repository/api/branch-repository.mappers";
import { getBranchRepositoryHealthFromApi } from "@/entities/repository/api/get-branch-repository-health-from-api";
import type { BranchRepositoryHealth } from "@/entities/repository/domain/model/branch-repository";
import {
  REPOSITORY_OPERATIONAL_ERRORS,
  REPOSITORY_SYNC_STATUS_ERROR_VALUE,
  REPOSITORY_SYNC_STATUS_SYNCING,
} from "@/entities/repository/domain/model/repository";
import { toBranchRepositoriesError } from "@/entities/repository/domain/rules/branch-repositories-error";
import { getRepositoryListKind } from "@/entities/repository/domain/rules/get-repository-list-kind";

export interface GetBranchRepositoryHealthParams extends BranchContextParams {
  syncWithGit: boolean;
  limit: number;
}

export type GetBranchRepositoryHealth = (
  params: GetBranchRepositoryHealthParams
) => Promise<BranchRepositoryHealth>;

export const getBranchRepositoryHealth: GetBranchRepositoryHealth = async ({
  branchName,
  syncWithGit,
  limit,
}) => {
  const data = await getBranchRepositoryHealthFromApi({
    branchName,
    kind: getRepositoryListKind(syncWithGit),
    importErrorStatuses: [REPOSITORY_SYNC_STATUS_ERROR_VALUE],
    unreachableStatuses: [...REPOSITORY_OPERATIONAL_ERRORS],
    syncingStatuses: [REPOSITORY_SYNC_STATUS_SYNCING],
    limit,
  }).catch((error: unknown) => {
    throw toBranchRepositoriesError(error);
  });

  return {
    importErrors: toBranchRepositories(data.importErrors),
    importErrorCount: data.importErrors.count,
    unreachable: toBranchRepositories(data.unreachable),
    unreachableCount: data.unreachable.count,
    syncingCount: data.syncing.count,
  };
};
