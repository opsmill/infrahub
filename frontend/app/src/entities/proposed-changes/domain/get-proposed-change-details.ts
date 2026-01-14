import type { NodeMetadata } from "@/entities/nodes/types";
import {
  getProposedChangeDetailsFromApi,
  type ProposedChangeDetailsFromApiParams,
} from "@/entities/proposed-changes/api/get-proposed-change-details-from-api";

export type GetProposedChangeDetailsParams = ProposedChangeDetailsFromApiParams;

export type GetProposedChangeDetailsResponse = Awaited<ReturnType<typeof getProposedChangeDetails>>;

export const getProposedChangeDetails = async (params: GetProposedChangeDetailsParams) => {
  const { data, errors } = await getProposedChangeDetailsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const proposedChangeData = data.CoreProposedChange.edges?.[0]?.node;

  if (!proposedChangeData) {
    throw new Error("No proposed change found");
  }

  const proposedChangeMetadata = data.CoreProposedChange.edges[0]?.node_metadata;
  if (!proposedChangeMetadata) {
    throw new Error("No proposed change metadata found");
  }

  return {
    proposedChangeData,
    metadata: proposedChangeMetadata as NodeMetadata,
    tasksCount: data.InfrahubTask.count,
  };
};
