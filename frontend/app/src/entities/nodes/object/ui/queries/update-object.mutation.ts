import { useMutation } from "@tanstack/react-query";

import type { MutationConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type UpdateObjectParams,
  updateObject,
} from "@/entities/nodes/object/domain/update-object";

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
