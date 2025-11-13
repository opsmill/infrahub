import {
  getProposedChangeDetailsFromApi,
  type ProposedChangeDetailsFromApiParams,
  type ProposedChangeDetailsFromApiResponse,
} from "@/entities/proposed-changes/api/get-proposed-change-details-from-api";

export type GetProposedChangeDetailsParams = ProposedChangeDetailsFromApiParams;

export type GetProposedChangeDetailsResponse = {
  tasksCount: number;
  proposedChangeData: ProposedChangeDetailsFromApiResponse["CoreProposedChange"]["edges"][0]["node"];
};

export type GetProposedChangeDetails = (
  params: GetProposedChangeDetailsParams
) => Promise<GetProposedChangeDetailsResponse>;

export const getProposedChangeDetails: GetProposedChangeDetails = async (params) => {
  const { data, errors } = await getProposedChangeDetailsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const proposedChangeData = data.CoreProposedChange.edges?.[0]?.node;

  if (!proposedChangeData) {
    throw new Error("No proposed change found");
  }

  return {
    proposedChangeData,
    tasksCount: data.InfrahubTask.count,
  };
};
