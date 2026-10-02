import type { BranchContextParams } from "@/shared/api/types";

import { toBranchRepositories } from "@/entities/repository/api/branch-repository.mappers";
import { getBranchRepositoryHealthFromApi } from "@/entities/repository/api/get-branch-repository-health-from-api";
import type { BranchRepositoryHealth } from "@/entities/repository/domain/model/branch-repository";
import {
  REPOSITORY_OPERATIONAL_ERRORS,
  REPOSITORY_SYNC_STATUS_ERROR_VALUE,
  REPOSITORY_SYNC_STATUS_SYNCING,
} from "@/entities/repository/domain/model/repository";
import { getRepositoryListKind } from "@/entities/repository/domain/rules/get-repository-list-kind";

export interface GetBranchRepositoryHealthParams extends BranchContextParams {
  syncWithGit: boolean;
}

export type GetBranchRepositoryHealth = (
  params: GetBranchRepositoryHealthParams
) => Promise<BranchRepositoryHealth>;

export const getBranchRepositoryHealth: GetBranchRepositoryHealth = async ({
  branchName,
  syncWithGit,
}) => {
  const data = await getBranchRepositoryHealthFromApi({
    branchName,
    kind: getRepositoryListKind(syncWithGit),
    importErrorStatuses: [REPOSITORY_SYNC_STATUS_ERROR_VALUE],
    unreachableStatuses: [...REPOSITORY_OPERATIONAL_ERRORS],
    syncingStatuses: [REPOSITORY_SYNC_STATUS_SYNCING],
  });

  return {
    importErrors: toBranchRepositories(data.importErrors),
    unreachable: toBranchRepositories(data.unreachable),
    syncingCount: data.syncing.count,
  };
};
