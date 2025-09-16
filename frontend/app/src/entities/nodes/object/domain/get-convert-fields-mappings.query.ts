import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getConvertFieldsMapping } from "@/entities/nodes/object/domain/get-convert-fields-mappings";

interface FieldsMappingProps {
  sourceKind: string;
  targetKind: string;
}

interface FieldsMappingOptionsParams extends ContextParams, FieldsMappingProps {}

export function getConvertFieldsMappingOptions({
  sourceKind,
  targetKind,
  branchName,
  atDate,
}: FieldsMappingOptionsParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "fields-mapping-type-conversion", sourceKind, targetKind],
    queryFn: () => {
      return getConvertFieldsMapping({
        sourceKind,
        targetKind,
        branchName,
        atDate,
      });
    },
    enabled: Boolean(sourceKind && targetKind),
  });
}

export const useFieldsMappingTypeConversion = ({ sourceKind, targetKind }: FieldsMappingProps) => {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getConvertFieldsMappingOptions({
      sourceKind,
      targetKind,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
};
