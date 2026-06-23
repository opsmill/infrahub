import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";
import type { MutationConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type UpdateObjectParams,
  updateObject,
} from "@/entities/nodes/object/domain/update-object";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { objectItemEditQueryKeys } from "@/entities/nodes/object-item-edit/ui/queries/object-item-edit.query-keys";

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
    onSuccess: async (data, variables, onMutateResult, mutationContext) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: objectItemEditQueryKeys.all }),
        queryClient.invalidateQueries({ queryKey: objectQueryKeys.all }),
      ]);
      await config?.onSuccess?.(data, variables, onMutateResult, mutationContext);
    },
  });
}
