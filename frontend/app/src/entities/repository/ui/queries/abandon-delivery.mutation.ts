import { useMutation } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import {
  type AbandonDeliveryParams,
  abandonDelivery,
} from "@/entities/repository/domain/use-cases/abandon-delivery";

interface AbandonDeliveryProps extends MutationConfig<typeof abandonDelivery> {}

export const ABANDON_DELIVERY_MUTATION_KEY = ["repository", "abandon-delivery"] as const;

// The pending pushes live on the default branch, and the backend refuses an abandonment sent on any other.
export function useAbandonDeliveryMutation(config?: Omit<AbandonDeliveryProps, "mutationFn">) {
  const defaultBranch = useDefaultBranch();

  return useMutation({
    mutationKey: ABANDON_DELIVERY_MUTATION_KEY,
    mutationFn: (params: Omit<AbandonDeliveryParams, keyof BranchContextParams>) => {
      if (!defaultBranch) {
        throw new Error("The default branch is not loaded.");
      }
      return abandonDelivery({ branchName: defaultBranch.name, ...params });
    },
    ...config,
  });
}
