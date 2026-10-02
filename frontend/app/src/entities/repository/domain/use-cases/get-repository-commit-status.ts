import {
  type GetRepositoryCommitStatusFromApiParams,
  getRepositoryCommitStatusFromApi,
} from "@/entities/repository/api/get-repository-commit-status-from-api";
import type { RepositoryCommitStatus } from "@/entities/repository/domain/model/repository";

export type GetRepositoryCommitStatusParams = GetRepositoryCommitStatusFromApiParams;

export type GetRepositoryCommitStatus = (
  params: GetRepositoryCommitStatusParams
) => Promise<RepositoryCommitStatus>;

export const getRepositoryCommitStatus: GetRepositoryCommitStatus = async (params) => {
  const { data, errors } = await getRepositoryCommitStatusFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((error) => error.message).join("; "));
  }

  if (!data?.InfrahubRepositoryCommits) {
    throw new Error("The commit log response carried no status");
  }

  const { condition, pending_count, unavailable } = data.InfrahubRepositoryCommits;
  return { condition, pending_count, unavailable };
};
