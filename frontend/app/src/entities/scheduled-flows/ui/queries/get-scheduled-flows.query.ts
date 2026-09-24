import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { getScheduledFlows } from "@/entities/scheduled-flows/domain/use-cases/get-scheduled-flows";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export function getScheduledFlowsQueryOptions() {
  return queryOptions({
    queryKey: tasksQueryKeys.scheduledFlows(),
    queryFn: () => getScheduledFlows(),
  });
}

export function useGetScheduledFlows(config?: QueryConfig<typeof getScheduledFlowsQueryOptions>) {
  return useQuery({
    ...getScheduledFlowsQueryOptions(),
    ...config,
  });
}
