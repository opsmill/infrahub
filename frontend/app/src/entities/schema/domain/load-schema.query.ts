import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type LoadSchemaParams, loadSchema } from "@/entities/schema/domain/load-schema";

export interface LoadSchemaQueryOptionsParams extends LoadSchemaParams {
  schemaHash: string | undefined;
}

export function loadSchemaQueryOptions({
  branchName,
  atDate,
  schemaHash,
}: LoadSchemaQueryOptionsParams) {
  return queryOptions({
    queryKey: [schemaHash, "schema"],
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
