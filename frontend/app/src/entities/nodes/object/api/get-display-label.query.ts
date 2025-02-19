import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getDisplayLabelFromApi } from "./get-display-label";

type DisplayLabelProps = { objectid: string; kind: string; enabled?: boolean };

export function getDisplayLabelQueryOptions({ objectid, kind, enabled }: DisplayLabelProps) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["display-label", objectid, kind],
    queryFn: () => {
      return getDisplayLabelFromApi({
        objectid,
        kind,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
    enabled,
  });
}

export const useDisplayLabel = ({ objectid, kind, enabled }: DisplayLabelProps) => {
  const { data, ...props } = useQuery(getDisplayLabelQueryOptions({ objectid, kind, enabled }));

  const object = data?.data?.[kind]?.edges?.[0]?.node ?? {};

  return {
    data: object,
    ...props,
  };
};
