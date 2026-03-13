import { useMutation } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type ConvertObjectParams,
  convertObject,
} from "@/entities/nodes/convert/domain/convert-object";

export function useConvertObjectMutation() {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<ConvertObjectParams, "branchName">) => {
      return convertObject({
        branchName: currentBranch.name,
        ...params,
      });
    },
  });
}
