import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import {
  type PlaceRackItemParams,
  placeRackItem,
} from "@/entities/rack-elevation/domain/use-cases/place-rack-item";
import { rackElevationQueryKeys } from "@/entities/rack-elevation/ui/queries/rack-elevation.query-keys";

export function usePlaceRackItemMutation() {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<PlaceRackItemParams, "branchName">) =>
      placeRackItem({ branchName: currentBranch.name, ...params }),
    onSuccess: (_result, { rackId }) => {
      queryClient.invalidateQueries({ queryKey: rackElevationQueryKeys.elevations({ rackId }) });
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });
}
