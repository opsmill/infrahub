import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { CreateObjectParams, createObject } from "@/entities/nodes/object/domain/create-object";
import { useMutation } from "@tanstack/react-query";

export function useCreateObjectMutation() {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<CreateObjectParams, "branchName">) => {
      return createObject({
        branchName: currentBranch.name,
        ...params,
      });
    },
  });
}
