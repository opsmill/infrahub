import { useQuery } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectsCountQueryOptions } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_ERROR_IMPORT_FILTER,
} from "@/entities/repository/domain/model/repository";
import {
  deriveRepositorySyncIndicator,
  type RepositorySyncIndicator,
} from "@/entities/repository/domain/rules/derive-repository-sync-indicator";

const REFETCH_INTERVAL = 10_000;

export function useRepositorySyncIndicator(): RepositorySyncIndicator {
  const { currentBranch } = useCurrentBranch();

  // `atDate: null` keeps both counts on current state, whatever time frame is selected.
  const countOptions = (filters?: typeof REPOSITORY_ERROR_IMPORT_FILTER) =>
    getObjectsCountQueryOptions({
      objectKind: GENERIC_REPOSITORY_KIND,
      branchName: currentBranch.name,
      atDate: null,
      ...(filters ? { filters: [filters] } : {}),
    });

  const total = useQuery({ ...countOptions(), refetchInterval: REFETCH_INTERVAL });
  const failing = useQuery({
    ...countOptions(REPOSITORY_ERROR_IMPORT_FILTER),
    refetchInterval: REFETCH_INTERVAL,
  });

  return deriveRepositorySyncIndicator({
    totalIsPending: total.isPending,
    totalError: total.error,
    totalCount: total.data,
    failingIsPending: failing.isPending,
    failingError: failing.error,
    failingCount: failing.data,
  });
}
