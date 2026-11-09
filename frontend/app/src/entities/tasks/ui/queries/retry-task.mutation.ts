import { useMutation } from "@tanstack/react-query";

import type { MutationConfig } from "@/shared/api/types";

import { type RetryTaskParams, retryTask } from "@/entities/tasks/domain/retry-task/retry-task";

export const RETRY_TASK_MUTATION_KEY = ["tasks", "retry"] as const;

export function useRetryTaskMutation(
  config?: Omit<MutationConfig<typeof retryTask>, "mutationFn">
) {
  return useMutation({
    mutationKey: RETRY_TASK_MUTATION_KEY,
    mutationFn: (params: RetryTaskParams) => retryTask(params),
    ...config,
  });
}
