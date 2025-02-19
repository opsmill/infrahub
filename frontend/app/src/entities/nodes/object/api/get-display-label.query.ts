import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getDisplayLabelFromApi } from "./get-display-label";

export function getDisplayLabelQueryOptions({
  objectid,
  kind,
}: { objectid: string; kind: string }) {
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
  });
}

export const useDisplayLabel = ({ objectid, kind }: { objectid: string; kind: string }) => {
  const { data, ...props } = useQuery(getDisplayLabelQueryOptions({ objectid, kind }));

  const object = data?.data?.[kind]?.edges?.[0]?.node ?? {};

  return {
    data: object,
    ...props,
  };
};
