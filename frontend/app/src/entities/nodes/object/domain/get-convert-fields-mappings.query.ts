import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getConvertFieldsMapping } from "@/entities/nodes/object/domain/get-convert-fields-mappings";
import {
  ObjectConvertFieldsMappingProps,
  objectQueryKeys,
} from "@/entities/nodes/object/domain/object.query-keys";

interface FieldsMappingProps {
  sourceKind: string;
  targetKind: string;
}

export function getConvertFieldsMappingOptions({
  sourceKind,
  targetKind,
  branchName,
  atDate,
}: ObjectConvertFieldsMappingProps) {
  return queryOptions({
    queryKey: objectQueryKeys.convert({
      sourceKind,
      targetKind,
      branchName,
      atDate,
    }),
    queryFn: () => {
      return getConvertFieldsMapping({
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

  return useQuery(
    getConvertFieldsMappingOptions({
      sourceKind,
      targetKind,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
};
