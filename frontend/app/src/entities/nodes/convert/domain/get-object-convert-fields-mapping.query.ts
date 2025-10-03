import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  GetObjectConvertFieldsMapping,
  type GetObjectConvertFieldsMappingParams,
} from "@/entities/nodes/convert/domain/get-object-convert-fields-mapping";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

export function getConvertFieldsMappingOptions(params: GetObjectConvertFieldsMappingParams) {
  return queryOptions({
    queryKey: objectQueryKeys.convert(params),
    queryFn: () => GetObjectConvertFieldsMapping(params),
  });
}

export const useGetObjectConvertFieldsMapping = (
  params: Omit<GetObjectConvertFieldsMappingParams, keyof ContextParams>
) => {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getConvertFieldsMappingOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
};
