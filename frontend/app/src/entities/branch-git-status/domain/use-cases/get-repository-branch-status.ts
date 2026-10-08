import { getRepositoryBranchStatusFromApi } from "@/entities/branch-git-status/api/get-repository-branch-status-from-api";
import { toRepositoryBranchStatusPage } from "@/entities/branch-git-status/api/repository-branch-status.mappers";
import type { RepositoryBranchStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-status";
import { toBranchGitStatusError } from "@/entities/branch-git-status/domain/rules/to-branch-git-status-error";

export interface GetRepositoryBranchStatusParams {
  repositoryId: string;
  limit: number;
}

export type GetRepositoryBranchStatus = (
  params: GetRepositoryBranchStatusParams
) => Promise<RepositoryBranchStatusPage>;

export const getRepositoryBranchStatus: GetRepositoryBranchStatus = async ({
  repositoryId,
  limit,
}) => {
  const connection = await getRepositoryBranchStatusFromApi({ id: repositoryId, limit }).catch(
    (error: unknown) => {
      throw toBranchGitStatusError(error, "Failed to load the repository branch status");
    }
  );

  return toRepositoryBranchStatusPage(connection);
};
