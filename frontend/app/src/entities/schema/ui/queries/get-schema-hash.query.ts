import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetSchemaHashParams, getSchemaHash } from "@/entities/schema/domain/get-schema-hash";
import { schemaQueryKeys } from "@/entities/schema/ui/queries/schema.query-keys";

export function getSchemaHashQueryOptions({ branchName, atDate }: GetSchemaHashParams) {
  return queryOptions({
    queryKey: schemaQueryKeys.hash({ branchName, atDate }),
    queryFn: async () => {
      return getSchemaHash({ branchName, atDate });
    },
  });
}

export type UseGetSchemaHashConfig = QueryConfig<typeof getSchemaHashQueryOptions>;

export function useGetSchemaHash(config?: UseGetSchemaHashConfig) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getSchemaHashQueryOptions({ branchName: currentBranch.name, atDate }),
    ...config,
  });
}
