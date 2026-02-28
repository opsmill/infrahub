import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRelationshipPropertiesParams,
  getRelationshipProperties,
} from "@/entities/nodes/relationships/domain/get-relationship-properties/get-relationship-properties";
import { relationshipsQueryKeys } from "@/entities/nodes/relationships/ui/queries/relationships.query-keys";

export type UseGetRelationshipPropertiesParams = Omit<
  GetRelationshipPropertiesParams,
  "branchName" | "atDate"
>;

export function getRelationshipPropertiesQueryOptions(params: GetRelationshipPropertiesParams) {
  return queryOptions({
    queryKey: relationshipsQueryKeys.properties({
      ...params,
      objectKind: params.parentKind,
      objectId: params.parentId,
    }),
    queryFn: () => getRelationshipProperties(params),
  });
}

export function useGetRelationshipProperties(params: UseGetRelationshipPropertiesParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getRelationshipPropertiesQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
