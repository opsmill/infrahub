import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  type GetEventDetailsParams,
  getEventDetails,
} from "@/entities/events/domain/get-event-details";

export function getEventDetailsQueryOptions(params: GetEventDetailsParams) {
  return queryOptions({
    queryKey: ["events", params.id],
    queryFn: () => {
      return getEventDetails(params);
    },
  });
}

export const useGetEventDetails = (params: GetEventDetailsParams) => {
  return useQuery(getEventDetailsQueryOptions(params));
};
