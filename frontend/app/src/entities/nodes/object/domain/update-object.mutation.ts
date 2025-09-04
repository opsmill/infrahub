import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { UpdateObjectParams, updateObject } from "@/entities/nodes/object/domain/update-object";
import { MutationConfig } from "@/shared/api/types";
import { useMutation } from "@tanstack/react-query";

interface UpdateObjectProps extends MutationConfig<typeof updateObject> {}

export const UPDATE_OBJECT_MUTATION_KEY = ["objects", "update"] as const;

export function useUpdateObjectMutation(config?: Omit<UpdateObjectProps, "mutationFn">) {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationKey: UPDATE_OBJECT_MUTATION_KEY,
    mutationFn: (params: Omit<UpdateObjectParams, "branchName">) => {
      return updateObject({
        branchName: currentBranch.name,
        ...params,
      });
    },
    ...config,
  });
}
