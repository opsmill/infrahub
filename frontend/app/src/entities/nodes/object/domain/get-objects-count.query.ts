import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { GetObjectsCountParams, getObjectsCount } from "./get-objects-count";

export function getObjectsCountQueryOptions({
  objectKind,
  filters,
  branchName,
  atDate,
}: GetObjectsCountParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "objects", objectKind, "count", JSON.stringify(filters)],
    queryFn: async () => {
      return getObjectsCount({
        objectKind,
        branchName,
        atDate,
        filters,
      });
    },
  });
}

export function useObjectsCount(params: Omit<GetObjectsCountParams, "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getObjectsCountQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
