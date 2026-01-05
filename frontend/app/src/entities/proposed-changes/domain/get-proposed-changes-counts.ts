import {
  getProposedChangesCountsFromApi,
  type ProposedChangesCountsFromApiParams,
} from "@/entities/proposed-changes/api/get-proposed-changes-counts-from-api";

export type GetProposedChangesCountsParams = ProposedChangesCountsFromApiParams;

export type GetProposedChangesCountsResponse = {
  opened: number;
  closed: number;
};

export type GetProposedChangesCounts = (
  params: GetProposedChangesCountsParams
) => Promise<GetProposedChangesCountsResponse>;

export const getProposedChangesCounts: GetProposedChangesCounts = async (
  params: ProposedChangesCountsFromApiParams
) => {
  const { data, errors } = await getProposedChangesCountsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return {
    opened: data.opened.count ?? 0,
    closed: data.closed.count ?? 0,
  };
};
