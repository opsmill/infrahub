import { useMutation } from "@tanstack/react-query";

import type { MutationConfig } from "@/shared/api/types";

import {
  type CheckConnectivityParams,
  checkConnectivity,
} from "@/entities/repository/domain/check-connectivity";

interface CheckConnectivityProps extends MutationConfig<typeof checkConnectivity> {}

export const CHECK_CONNECTIVITY_MUTATION_KEY = ["repository", "check-connectivity"] as const;

// invalidation-at-callsite: this is a probe — it surfaces transient connectivity
// info to the user and does not mutate any cached server state, so there is
// nothing to invalidate. Callsites still receive the response via the standard
// mutation API.
export function useCheckConnectivityMutation(config?: Omit<CheckConnectivityProps, "mutationFn">) {
  return useMutation({
    mutationKey: CHECK_CONNECTIVITY_MUTATION_KEY,
    mutationFn: (params: CheckConnectivityParams) => {
      return checkConnectivity(params);
    },
    ...config,
  });
}
