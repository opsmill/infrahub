import type { EventType } from "@/entities/events/types";

import { type GetEventsFromApiParams, getEventsFromApi } from "../api/get-events-from-api";
import { INFRAHUB_EVENT } from "../constants";

export type GetEventsParams = GetEventsFromApiParams;
export type GetEvents = (params: GetEventsParams) => Promise<Array<EventType>>;

export const getEvents: GetEvents = async (params) => {
  const { data } = await getEventsFromApi(params);

  return data[INFRAHUB_EVENT].edges.map((edge) => {
    return edge.node as EventType;
  });
};
