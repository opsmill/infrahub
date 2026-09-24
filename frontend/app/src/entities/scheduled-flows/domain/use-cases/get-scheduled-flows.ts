import { getScheduledFlowsFromApi } from "@/entities/scheduled-flows/api/get-scheduled-flows-from-api";

export const getScheduledFlows = async () => {
  const { data, errors } = await getScheduledFlowsFromApi();

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return {
    flows: data.InfrahubScheduledFlows.edges.map(({ node }) => node).filter((n) => !!n),
    catalogueOnly: data.InfrahubScheduledFlows.catalogue_only,
    count: data.InfrahubScheduledFlows.count,
  };
};

export type ScheduledFlowsResult = Awaited<ReturnType<typeof getScheduledFlows>>;
export type ScheduledFlowItem = ScheduledFlowsResult["flows"][number];
