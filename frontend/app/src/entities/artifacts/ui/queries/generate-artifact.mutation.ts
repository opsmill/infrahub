import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type GenerateArtifactParams,
  generateArtifact,
} from "@/entities/artifacts/domain/generate-artifact";
import { artifactsQueryKeys } from "@/entities/artifacts/ui/queries/artifacts.query-keys";
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
      // Generation enqueues a background task and (eventually) updates artifact storage.
      queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: artifactsQueryKeys.all });
    },
  });
};
