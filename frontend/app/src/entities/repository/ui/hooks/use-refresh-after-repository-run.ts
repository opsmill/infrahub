import { useQuery, useQueryClient } from "@tanstack/react-query";
import React from "react";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { getRepositoryActivityQueryOptions } from "@/entities/repository/ui/queries/get-repository-activity.query";
import {
  repositoriesQueryKeys,
  repositoryQueryKeys,
} from "@/entities/repository/ui/queries/repository.query-keys";

export interface UseRefreshAfterRepositoryRunParams {
  repositoryId: string;
}

/** The commit list, branch statuses and repository details do not poll, so a finished run leaves them stale. */
export function useRefreshAfterRepositoryRun({ repositoryId }: UseRefreshAfterRepositoryRunParams) {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();
  // Reads the activity the card already polls; this observer adds no polling of its own.
  const { data } = useQuery({
    ...getRepositoryActivityQueryOptions({ id: repositoryId, branchName: currentBranch.name }),
    refetchInterval: false,
  });
  // Last runs are newest first, so this changes when a run finishes; null means none is recorded yet.
  const latestFinishedAt = data && (data.lastRuns[0]?.finishedAt ?? null);
  const seenLatestFinishedAtRef = React.useRef(latestFinishedAt);

  React.useEffect(() => {
    const seen = seenLatestFinishedAtRef.current;
    seenLatestFinishedAtRef.current = latestFinishedAt;
    if (seen === undefined || latestFinishedAt === undefined || seen === latestFinishedAt) return;

    queryClient.invalidateQueries({
      queryKey: repositoriesQueryKeys.repository({ repositoryId, branchName: currentBranch.name }),
    });
    queryClient.invalidateQueries({ queryKey: repositoryQueryKeys.branchStatuses() });
    queryClient.invalidateQueries({
      queryKey: objectQueryKeys.all,
      predicate: ({ queryKey }) => queryKey.includes(repositoryId),
    });
  }, [latestFinishedAt, queryClient, repositoryId, currentBranch.name]);
}
