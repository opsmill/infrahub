import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRackElevationKindsParams,
  getRackElevationKinds,
} from "@/entities/rack-elevation/domain/use-cases/get-rack-elevation-kinds";
import { rackElevationQueryKeys } from "@/entities/rack-elevation/ui/queries/rack-elevation.query-keys";

export function getRackElevationKindsQueryOptions(params: GetRackElevationKindsParams) {
  return queryOptions({
    queryKey: rackElevationQueryKeys.kinds(params),
    queryFn: () => getRackElevationKinds(params),
  });
}

export function useGetRackElevationKinds() {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getRackElevationKindsQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
