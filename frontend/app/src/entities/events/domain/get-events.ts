import {
  type GetEventsFromApiParams,
  getEventsFromApi,
} from "@/entities/events/api/get-events-from-api";
import type { EventType } from "@/entities/events/domain/model/event";
import { INFRAHUB_EVENT } from "@/entities/events/domain/model/event-constants";

export type GetEventsParams = GetEventsFromApiParams;
export type GetEvents = (params: GetEventsParams) => Promise<Array<EventType>>;

export const getEvents: GetEvents = async (params) => {
  const { data } = await getEventsFromApi(params);

  return data[INFRAHUB_EVENT].edges.map((edge) => {
    return edge.node as EventType;
  });
};
