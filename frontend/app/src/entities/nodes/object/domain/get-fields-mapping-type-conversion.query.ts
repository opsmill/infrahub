import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getFieldsMappingFromApi } from "@/entities/nodes/object/api/get-fields-mapping-type-conversion-from-api";

interface FieldsMappingProps {
  sourceKind: string;
  targetKind: string;
}

interface FieldsMappingOptionsParams extends ContextParams, FieldsMappingProps {}

export function getFieldsMappingOptions({
  sourceKind,
  targetKind,
  branchName,
  atDate,
}: FieldsMappingOptionsParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "fields-mapping-type-conversion", sourceKind, targetKind],
    queryFn: () => {
      return getFieldsMappingFromApi({
        sourceKind,
        targetKind,
        branchName,
        atDate,
      });
    },
  });
}

export const useFieldsMappingTypeConversion = ({ sourceKind, targetKind }: FieldsMappingProps) => {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  const { data, ...props } = useQuery(
    getFieldsMappingOptions({
      sourceKind,
      targetKind,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );

  const result = data?.data?.FieldsMappingTypeConversion?.mapping ?? {};

  return {
    data: result,
    ...props,
  };
};
