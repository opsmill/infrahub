import { queryOptions, useQuery } from "@tanstack/react-query";

import { retryBackgroundQuery } from "@/shared/api/background-query";

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
    retry: retryBackgroundQuery,
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[2].branchName === params.branchName ? previousData : undefined,
  });
}

export function useGetRepositoryNames(params: GetRepositoryNamesParams) {
  return useQuery(getRepositoryNamesQueryOptions(params));
}
