import { queryOptions } from "@tanstack/react-query";

import { getRepositorySyncHealth } from "@/entities/repository/domain/use-cases/get-repository-sync-health";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export const getRepositorySyncHealthQueryOptions = (branch: string) => {
  return queryOptions({
    queryKey: repositoryQueryKeys.syncHealth(branch),
    queryFn: () => getRepositorySyncHealth(branch),
  });
};
