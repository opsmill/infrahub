import { getEventsFromApi } from "@/entities/events/api/get-events-from-api";
import { INFRAHUB_EVENT } from "@/entities/events/constants";
import type { EventType } from "@/entities/events/types";

export type GetEventDetailsParams = {
  id: string;
};

export type GetEventDetails = (params: GetEventDetailsParams) => Promise<EventType>;

export const getEventDetails: GetEventDetails = async ({ id }) => {
  const { data, errors } = await getEventsFromApi({
    ids: [id],
  });

  if (errors && errors[0]) {
    throw new Error(errors[0].message);
  }

  const eventNode = data?.[INFRAHUB_EVENT]?.edges?.[0]?.node;

  if (!eventNode) {
    throw new Error(`Event id ${id} not found`);
  }

  return eventNode as EventType;
};
