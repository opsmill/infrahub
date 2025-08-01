import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { GetProposedChangeActionFromApiParams } from "../api/get-proposed-changes-available-actions-from-api";
import { getProposedChangeAvailableActions } from "./get-proposed-change-available-actions";

export function getProposedChangeAvailableActionsQueryOptions({
  atDate,
}: GetProposedChangeActionFromApiParams) {
  return queryOptions({
    queryKey: [atDate, "objects", PROPOSED_CHANGE_OBJECT, "actions"],
    queryFn: () => {
      return getProposedChangeAvailableActions({
        atDate,
      });
    },
  });
}

export function useGetProposedChangeAvailableActions() {
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getProposedChangeAvailableActionsQueryOptions({
      atDate: timeMachineDate,
    })
  );
}
