import { queryOptions, useQuery } from "@tanstack/react-query";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { REPOSITORY_KIND } from "@/shared/config/constants";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { relationshipsQueryKeys } from "@/entities/nodes/relationships/ui/queries/relationships.query-keys";
import { REPOSITORY_OBJECTS_TAB } from "@/entities/repository/constants";
import {
  type GetRepositoryGroupParams,
  getRepositoryGroup,
} from "@/entities/repository/domain/get-repository-group";

export function getRepositoryGroupQueryOption(params: GetRepositoryGroupParams) {
  return queryOptions({
    queryKey: relationshipsQueryKeys.lists({
      branchName: params.branchName,
      atDate: null,
      objectKind: REPOSITORY_KIND,
      objectId: params.nodeId,
      relationshipName: REPOSITORY_OBJECTS_TAB,
    }),
    queryFn: () => getRepositoryGroup(params),
  });
}

export type useGetRepositoryGroupOptions = QueryConfig<typeof getRepositoryGroupQueryOption>;

export function useGetRepositoryGroup(
  params: Omit<GetRepositoryGroupParams, keyof ContextParams>,
  config: useGetRepositoryGroupOptions = {}
) {
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    ...getRepositoryGroupQueryOption({ ...params, branchName: currentBranch.name }),
    ...config,
  });
}
