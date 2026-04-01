import { useMutation } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { triggerAITransformFromApi } from "@/entities/transforms/api/trigger-ai-transform-from-api";

export const useTriggerAITransformMutation = () => {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: { transformId: string }) => {
      return triggerAITransformFromApi({
        branchName: currentBranch.name,
        ...params,
      });
    },
  });
};
