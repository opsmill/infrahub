import { queryOptions, useQuery } from "@tanstack/react-query";

import { keepPreviousDataWithin } from "@/shared/api/keep-previous-data-within";

import {
  type GetRepositoryNamesParams,
  getRepositoryNames,
} from "@/entities/repository/domain/use-cases/get-repository-names";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export function getRepositoryNamesQueryOptions(params: GetRepositoryNamesParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.names(params),
    queryFn: () => getRepositoryNames(params),
    enabled: params.ids.length > 0,
    placeholderData: keepPreviousDataWithin(
      repositoryQueryKeys.namesOnBranch({ branchName: params.branchName })
    ),
  });
}

export function useGetRepositoryNames(params: GetRepositoryNamesParams) {
  return useQuery(getRepositoryNamesQueryOptions(params));
}
