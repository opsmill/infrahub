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
  const { data, errors } = await getProposedChangesFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const schemaKindToQuery = params.schema.kind as string;

  return data[schemaKindToQuery]?.edges?.map((edge: any) => edge.node) ?? [];
}
