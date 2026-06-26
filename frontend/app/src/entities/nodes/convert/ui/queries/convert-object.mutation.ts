import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type ConvertObjectParams,
  convertObject,
} from "@/entities/nodes/convert/domain/convert-object";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export function useConvertObjectMutation() {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<ConvertObjectParams, "branchName">) => {
      return convertObject({
        branchName: currentBranch.name,
        ...params,
      });
    },
    onSuccess: () => {
      // Conversion replaces the source node with a new one of the target kind;
      // every cached object list/detail can be affected.
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });
}
