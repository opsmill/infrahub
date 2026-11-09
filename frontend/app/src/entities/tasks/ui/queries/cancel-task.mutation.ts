import { useMutation } from "@tanstack/react-query";

import type { MutationConfig } from "@/shared/api/types";

import { type CancelTaskParams, cancelTask } from "@/entities/tasks/domain/cancel-task/cancel-task";

export const CANCEL_TASK_MUTATION_KEY = ["tasks", "cancel"] as const;

export function useCancelTaskMutation(
  config?: Omit<MutationConfig<typeof cancelTask>, "mutationFn">
) {
  return useMutation({
    mutationKey: CANCEL_TASK_MUTATION_KEY,
    mutationFn: (params: CancelTaskParams) => cancelTask(params),
    ...config,
  });
}
