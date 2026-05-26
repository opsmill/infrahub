import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { loadSchema } from "@/entities/schema/domain/load-schema";
import {
  type LoadSchemaQueryKeyParams,
  schemaQueryKeys,
} from "@/entities/schema/ui/queries/schema.query-keys";

export type LoadSchemaQueryOptionsParams = LoadSchemaQueryKeyParams;

export function loadSchemaQueryOptions({
  branchName,
  atDate,
  schemaHash,
}: LoadSchemaQueryOptionsParams) {
  return queryOptions({
    queryKey: schemaQueryKeys.load({ branchName, atDate, schemaHash }),
    queryFn: async () => {
      return loadSchema({ branchName, atDate });
    },
  });
}

export type UseLoadSchemaOptions = QueryConfig<typeof loadSchemaQueryOptions>;

export function useLoadSchema(schemaHash: string | undefined, config: UseLoadSchemaOptions = {}) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...loadSchemaQueryOptions({ branchName: currentBranch.name, atDate, schemaHash }),
    ...config,
  });
}
