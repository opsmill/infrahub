import {
  ProposedChangesCountsFromApiParams,
  getProposedChangesCountsFromApi,
} from "@/entities/proposed-changes/api/get-proposed-changes-counts-from-api";

type GetProposedChangesCountsResult = {
  opened: number;
  closed: number;
};

export async function getProposedChangesCounts(
  params: ProposedChangesCountsFromApiParams
): Promise<GetProposedChangesCountsResult> {
  const { data, errors } = await getProposedChangesCountsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return {
    opened: data.opened.count ?? 0,
    draft: data.draft.count ?? 0,
    closed: data.closed.count ?? 0,
  };
}
