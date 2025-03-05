import { GetEventsParams, getEventsFromApi } from "../api/get-events-from-api";
import { EventType } from "../ui/event";
import { INFRAHUB_EVENT } from "../utils/constants";

export type GetEvents = (params: GetEventsParams) => Promise<Array<EventType>>;

export const getEvents: GetEvents = async (params) => {
  const { data } = await getEventsFromApi(params);

  return data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node as EventType;
  });
};
