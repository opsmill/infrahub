import { useMutation } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type AllocateResourceParams,
  allocateResource,
} from "@/entities/resource-manager/domain/allocate-resource";

export function useAllocateResourceMutation() {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<AllocateResourceParams, "branchName">) => {
      return allocateResource({
        branchName: currentBranch.name,
        ...params,
      });
    },
  });
}
