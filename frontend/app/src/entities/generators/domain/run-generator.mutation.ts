import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { RunGeneratorParams, runGenerator } from "@/entities/generators/domain/run-generator";
import { useMutation } from "@tanstack/react-query";

export const useRunGeneratorMutation = () => {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: async ({
      generatorId,
      targetNodeIds,
    }: Omit<RunGeneratorParams, "branchName" | "waitUntilCompletion">) => {
      await runGenerator({
        branchName: currentBranch.name,
        waitUntilCompletion: true,
        generatorId,
        targetNodeIds,
      });
    },
  });
};
