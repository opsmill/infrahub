import { getRepositoryNamesFromApi } from "@/entities/repository/api/get-repository-names-from-api";

export interface GetRepositoryNamesParams {
  branchName: string;
  ids: string[];
}

export type GetRepositoryNames = (
  params: GetRepositoryNamesParams
) => Promise<Record<string, string>>;

// Ids that aren't repositories are simply absent from the result.
export const getRepositoryNames: GetRepositoryNames = (params) => getRepositoryNamesFromApi(params);
