import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import { getNodeLabelFromApi } from "./get-display-label";

type NodeLabelProps = {
  objectId?: string;
  kind: string;
  enabled?: boolean;
  branch?: string | null;
};

export function getNodeLabelQueryOptions({
  objectId,
  kind,
  enabled,
  branchName,
  atDate,
}: NodeLabelProps & ContextParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "display-label", objectId, kind],
    queryFn: () => {
      return getNodeLabelFromApi({
        objectId,
        kind,
        branchName,
        atDate,
      });
    },
    enabled,
  });
}

export const useNodeLabel = ({ objectId, kind, enabled, branch }: NodeLabelProps) => {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  const { data, ...props } = useQuery(
    getNodeLabelQueryOptions({
      objectId,
      kind,
      enabled,
      branchName: branch ?? currentBranch.name,
      atDate: timeMachineDate,
    })
  );

  const object = data?.data?.[kind]?.edges?.[0]?.node ?? {};

  return {
    data: object,
    ...props,
  };
};
