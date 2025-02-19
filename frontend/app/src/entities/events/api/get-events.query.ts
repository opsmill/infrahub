import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { EventType } from "../ui/event";
import { INFRAHUB_EVENT } from "../utils/constants";
import { getEventsFromApi } from "./get-events-from-api";

export function getEventsQueryOptions({
  ids,
  offset,
  limit,
  search,
}: { ids?: Array<string | undefined>; offset?: number; limit?: number; search?: string }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["events", ids, offset, limit, search],
    queryFn: () => {
      return getEventsFromApi({
        ids,
        offset,
        limit,
        search,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useEvents = ({
  ids = [],
  offset,
  limit,
  search,
}: { ids?: Array<string | undefined>; offset?: number; limit?: number; search?: string }) => {
  const { data } = useQuery(getEventsQueryOptions({ ids, offset, limit, search }));

  const activities: EventType[] = data?.data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node;
  });

  const count = data?.data?.[INFRAHUB_EVENT]?.count;

  return {
    ...useQuery(getEventsQueryOptions({ ids, offset, limit, search })),
    data: activities,
    count,
  };
};
