import { getRepositoryBranchStatusFromApi } from "@/entities/branch-git-status/api/get-repository-branch-status-from-api";
import { toRepositoryBranchGitStatusPage } from "@/entities/branch-git-status/api/repository-branch-status.mappers";
import type { RepositoryBranchGitStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-git-status";
import { toBranchGitStatusError } from "@/entities/branch-git-status/domain/rules/to-branch-git-status-error";

export interface GetRepositoryBranchStatusParams {
  repositoryId: string;
  limit: number;
}

export type GetRepositoryBranchStatusResult = RepositoryBranchGitStatusPage;

export type GetRepositoryBranchStatus = (
  params: GetRepositoryBranchStatusParams
) => Promise<GetRepositoryBranchStatusResult>;

export const getRepositoryBranchStatus: GetRepositoryBranchStatus = async ({
  repositoryId,
  limit,
}) => {
  const connection = await getRepositoryBranchStatusFromApi({ id: repositoryId, limit }).catch(
    (error: unknown) => {
      throw toBranchGitStatusError(error, "Failed to load the repository branch status");
    }
  );

  return toRepositoryBranchGitStatusPage(connection);
};
