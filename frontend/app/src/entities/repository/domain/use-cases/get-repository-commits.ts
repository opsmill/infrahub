import {
  type GetRepositoryCommitsFromApiParams,
  getRepositoryCommitsFromApi,
} from "@/entities/repository/api/get-repository-commits-from-api";
import { mapToRepositoryCommitLog } from "@/entities/repository/api/repository-commits.mappers";
import {
  type RepositoryCommitLog,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";

export type GetRepositoryCommitsParams = GetRepositoryCommitsFromApiParams;

export type GetRepositoryCommitsResult = RepositoryCommitLog;

export type GetRepositoryCommits = (
  params: GetRepositoryCommitsParams
) => Promise<GetRepositoryCommitsResult>;

export const getRepositoryCommits: GetRepositoryCommits = async (params) => {
  const { data, errors } = await getRepositoryCommitsFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((error) => error.message).join("; "));
  }

  if (!data?.InfrahubRepositoryCommits) {
    throw new Error("The commit log response carried no data");
  }

  const log = mapToRepositoryCommitLog(data.InfrahubRepositoryCommits);

  if (log.condition === RepositoryGitCondition.UNAVAILABLE) {
    throw new RepositoryGitUnavailableError(log);
  }

  return log;
};
