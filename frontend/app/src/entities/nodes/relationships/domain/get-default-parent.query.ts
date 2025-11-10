import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import {
  type DefaultParentParams,
  getDefaultParent,
  type UseDefaultParentParams,
} from "@/entities/nodes/relationships/domain/get-default-parent";

export function getDefaultParentQueryOptions(params: DefaultParentParams) {
  return queryOptions({
    queryKey: [
      ...objectQueryKeys.allWithContext(params),
      params.defaultValue?.value?.id,
      params.parentRelationship?.peer,
    ],
    queryFn: () => getDefaultParent(params),
  });
}

export function useDefaultParent(params: UseDefaultParentParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const formContext = useCurrentFormContext();

  return useQuery(
    getDefaultParentQueryOptions({
      ...params,
      parentSchema: formContext.parentSchema,
      parentData: formContext.parentData,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
