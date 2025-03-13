import {
  GetEventDetailsFromApiParams,
  getEventDetailsFromApi,
} from "@/entities/events/api/get-event-details-from-api";
import { INFRAHUB_EVENT } from "@/entities/events/constants";
import { EventType } from "@/entities/events/types";

export type GetEventDetailsParams = GetEventDetailsFromApiParams;

export type GetEventDetails = (params: GetEventDetailsParams) => Promise<EventType>;

export const getEventDetails: GetEventDetails = async (params) => {
  const { data, errors } = await getEventDetailsFromApi(params);

  if (errors && errors[0]) {
    throw new Error(errors[0].message);
  }

  const eventNode = data?.[INFRAHUB_EVENT]?.edges?.[0]?.node;

  if (!eventNode) {
    throw new Error(`Event id ${params.id} not found`);
  }

  return eventNode;
};
