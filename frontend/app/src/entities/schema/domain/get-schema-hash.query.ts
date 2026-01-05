import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai/index";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetSchemaHashParams, getSchemaHash } from "@/entities/schema/domain/get-schema-hash";

export function getSchemaHashQueryOptions({ branchName, atDate }: GetSchemaHashParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "schema", "hash"],
    queryFn: async () => {
      return getSchemaHash({ branchName, atDate });
    },
  });
}

export function useGetSchemaHash() {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery(getSchemaHashQueryOptions({ branchName: currentBranch.name, atDate }));
}
