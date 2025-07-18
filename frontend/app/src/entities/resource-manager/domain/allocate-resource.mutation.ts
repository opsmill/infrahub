import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  AllocateResourceParams,
  allocateResource,
} from "@/entities/resource-manager/domain/allocate-resource";
import { useMutation } from "@tanstack/react-query";

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
