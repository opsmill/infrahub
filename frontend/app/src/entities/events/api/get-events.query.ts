import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { EventType } from "../ui/event";
import { INFRAHUB_EVENT } from "../utils/constants";
import { GlobalEventsFilters, getEventsFromApi } from "./get-events-from-api";

export function getEventsQueryOptions(filters: GlobalEventsFilters) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["events", filters],
    queryFn: () => {
      return getEventsFromApi({
        ...filters,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useEvents = (filters: GlobalEventsFilters) => {
  const { data } = useQuery(getEventsQueryOptions(filters));

  const activities: EventType[] = data?.data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node;
  });

  const count = data?.data?.[INFRAHUB_EVENT]?.count;

  return {
    ...useQuery(getEventsQueryOptions(filters)),
    data: activities,
    count,
  };
};
