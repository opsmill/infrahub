import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { BranchContextParams } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import {
  type ApplyNumberPoolRangeChangesParams,
  applyNumberPoolRangeChanges,
} from "@/entities/resource-manager/domain/use-cases/apply-number-pool-range-changes";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function useApplyNumberPoolRangeChangesMutation() {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<ApplyNumberPoolRangeChangesParams, keyof BranchContextParams>) => {
      return applyNumberPoolRangeChanges({ branchName: currentBranch.name, ...params });
    },
    onSettled: (_result, _error, { poolId }) => {
      queryClient.invalidateQueries({
        queryKey: resourceManagerQueryKeys.numberPoolForEditing({
          branchName: currentBranch.name,
          poolId,
        }),
      });
      queryClient.invalidateQueries({ queryKey: resourceManagerQueryKeys.utilization({ poolId }) });
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });
}
