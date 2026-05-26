import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type GenerateArtifactParams,
  generateArtifact,
} from "@/entities/artifacts/domain/generate-artifact";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export const useGenerateArtifactMutation = () => {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<GenerateArtifactParams, "branchName">) => {
      return generateArtifact({
        branchName: currentBranch.name,
        ...params,
      });
    },
    onSuccess: () => {
      // Generation only enqueues a background task — artifact storage is not
      // updated until the task completes, so invalidating the artifacts list
      // here would just refetch stale data. Callers observing task status
      // should invalidate artifacts when the task transitions to success.
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
  });
};
