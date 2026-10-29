import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetNodeGeneratorDefinitionsParams,
  getNodeGeneratorDefinitions,
} from "@/entities/generators/domain/use-cases/get-node-generator-definitions";
import { generatorsQueryKeys } from "@/entities/generators/ui/queries/generator.query-keys";

export function getNodeGeneratorDefinitionsQueryOptions(params: GetNodeGeneratorDefinitionsParams) {
  return queryOptions({
    queryKey: generatorsQueryKeys.nodeDefinitions(params),
    queryFn: () => getNodeGeneratorDefinitions(params),
  });
}

export function useGetNodeGeneratorDefinitions(
  params: Omit<GetNodeGeneratorDefinitionsParams, keyof ContextParams>,
  config?: QueryConfig<typeof getNodeGeneratorDefinitionsQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getNodeGeneratorDefinitionsQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    ...config,
  });
}
