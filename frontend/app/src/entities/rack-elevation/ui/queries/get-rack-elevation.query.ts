import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRackElevationParams,
  getRackElevation,
} from "@/entities/rack-elevation/domain/use-cases/get-rack-elevation";
import { rackElevationQueryKeys } from "@/entities/rack-elevation/ui/queries/rack-elevation.query-keys";

export function getRackElevationQueryOptions(params: GetRackElevationParams) {
  return queryOptions({
    queryKey: rackElevationQueryKeys.elevation(params),
    queryFn: () => getRackElevation(params),
  });
}

export interface UseGetRackElevationParams {
  rackId: string;
  labelBy?: string | null;
  colorBy?: string | null;
}

export function useGetRackElevation({ rackId, labelBy, colorBy }: UseGetRackElevationParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getRackElevationQueryOptions({
      rackId,
      labelBy,
      colorBy,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
