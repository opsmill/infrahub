import {
  ProposedChangesFromApiParams,
  getProposedChangesFromApi,
} from "../api/get-proposed-changes-from-api";

type GetProposedChangesCountsResult = {
  opened: number;
  closed: number;
};

export async function getProposedChanges(
  params: ProposedChangesFromApiParams
): Promise<GetProposedChangesCountsResult> {
  const { data } = await getProposedChangesFromApi(params);

  const schemaKindToQuery = params.schema.kind as string;

  return data[schemaKindToQuery]?.edges?.map((edge: any) => edge.node) ?? [];
}
