import { useMutation } from "@tanstack/react-query";

import type { BranchContextParams, MutationConfig } from "@/shared/api/types";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import {
  type RetryDeliveryParams,
  retryDelivery,
} from "@/entities/repository/domain/use-cases/retry-delivery";

interface RetryDeliveryProps extends MutationConfig<typeof retryDelivery> {}

export const RETRY_DELIVERY_MUTATION_KEY = ["repository", "retry-delivery"] as const;

// The pending pushes live on the default branch, and the backend refuses a retry sent on any other.
export function useRetryDeliveryMutation(config?: Omit<RetryDeliveryProps, "mutationFn">) {
  const defaultBranch = useDefaultBranch();

  return useMutation({
    mutationKey: RETRY_DELIVERY_MUTATION_KEY,
    mutationFn: (params: Omit<RetryDeliveryParams, keyof BranchContextParams>) => {
      if (!defaultBranch) {
        throw new Error("The default branch is not loaded.");
      }
      return retryDelivery({ branchName: defaultBranch.name, ...params });
    },
    ...config,
  });
}
