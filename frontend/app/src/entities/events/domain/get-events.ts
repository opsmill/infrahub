import { GetEventsParams, getEventsFromApi } from "../api/get-events-from-api";
import { INFRAHUB_EVENT } from "../constants";
import { EventType } from "@/entities/events/types";

export type GetEvents = (params: GetEventsParams) => Promise<Array<EventType>>;

export const getEvents: GetEvents = async (params) => {
  const { data } = await getEventsFromApi(params);

  return data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node as EventType;
  });
};
