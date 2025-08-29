import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { UpdateObjectParams, updateObject } from "@/entities/nodes/object/domain/update-object";
import { MutationConfig } from "@/shared/api/types";
import { useMutation } from "@tanstack/react-query";

interface UpdateObjectProps extends MutationConfig<typeof updateObject> {}

export function useUpdateObjectMutation(config?: Omit<UpdateObjectProps, "mutationFn">) {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationKey: ["objects", "update"],
    mutationFn: (params: Omit<UpdateObjectParams, "branchName">) => {
      return updateObject({
        branchName: currentBranch.name,
        ...params,
      });
    },
    ...config,
  });
}
