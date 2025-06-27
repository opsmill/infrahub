import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  DefaultParentParams,
  UseDefaultParentParams,
  getDefaultParent,
} from "@/entities/nodes/relationships/domain/get-default-parent";
import { useFormContext } from "@/shared/components/form/utils/form-context";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

export function getDefaultParentQueryOptions(params: DefaultParentParams) {
  return queryOptions({
    queryKey: [
      params.branchName,
      params.atDate,
      "objects",
      params.defaultValue?.value?.id,
      params.parentRelationship?.peer,
    ],
    queryFn: () => getDefaultParent(params),
  });
}

export function useDefaultParent(params: UseDefaultParentParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const formContext = useFormContext();

  return useQuery({
    ...getDefaultParentQueryOptions({
      ...params,
      parentSchema: formContext.parentSchema,
      parentData: formContext.parentData,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
  });
}
