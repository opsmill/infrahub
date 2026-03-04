import { useMutation } from "@tanstack/react-query";

import {
  type GenerateArtifactParams,
  generateArtifact,
} from "@/entities/artifacts/domain/generate-artifact";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

export const useGenerateArtifactMutation = () => {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<GenerateArtifactParams, "branchName">) => {
      return generateArtifact({
        branchName: currentBranch.name,
        ...params,
      });
    },
  });
};
