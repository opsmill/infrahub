import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getNodeLabelFromApi } from "./get-display-label";

type NodeLabelProps = { objectid?: string; kind: string; enabled?: boolean };

export function getNodeLabelQueryOptions({ objectid, kind, enabled }: NodeLabelProps) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["display-label", objectid, kind],
    queryFn: () => {
      return getNodeLabelFromApi({
        objectid,
        kind,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
    enabled,
  });
}

export const useNodeLabel = ({ objectid, kind, enabled }: NodeLabelProps) => {
  const { data, ...props } = useQuery(getNodeLabelQueryOptions({ objectid, kind, enabled }));

  const object = data?.data?.[kind]?.edges?.[0]?.node ?? {};

  return {
    data: object,
    ...props,
  };
};
