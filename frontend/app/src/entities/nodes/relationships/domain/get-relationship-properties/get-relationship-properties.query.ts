import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  GetRelationshipPropertiesParams,
  getRelationshipProperties,
} from "@/entities/nodes/relationships/domain/get-relationship-properties/get-relationship-properties";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

export type UseGetRelationshipPropertiesParams = Omit<
  GetRelationshipPropertiesParams,
  "branchName" | "atDate"
>;

export function getRelationshipPropertiesQueryOptions(params: GetRelationshipPropertiesParams) {
  return queryOptions({
    queryKey: [
      params.branchName,
      params.atDate,
      "objects",
      params.parentKind,
      params.parentId,
      params.relationshipName,
      params.relationshipId,
      "properties",
    ],
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
