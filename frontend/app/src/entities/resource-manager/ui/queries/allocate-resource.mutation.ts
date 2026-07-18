import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import {
  type AllocateResourceParams,
  allocateResource,
} from "@/entities/resource-manager/domain/allocate-resource";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function useAllocateResourceMutation() {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<AllocateResourceParams, "branchName">) => {
      return allocateResource({
        branchName: currentBranch.name,
        ...params,
      });
    },
    onSuccess: () => {
      // Allocation changes pool utilization + creates a new resource node.
      queryClient.invalidateQueries({ queryKey: resourceManagerQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });
}
