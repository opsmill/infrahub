import { NodeCore } from "@/entities/nodes/types";
import {
  ProposedChangesFromApiParams,
  getProposedChangesFromApi,
} from "../api/get-proposed-changes-from-api";

export type ProposedChangeItem = {
  id: string;
  display_label: string;
  name: { value: string };
  created_by: { node: { display_label: string } };
  state: { value: string };
  is_draft: { value: string };
  _updated_at: string;
  source_branch: { value: string };
  approved_by: { edges: Array<{ node: NodeCore }> };
  total_comments: { value: number };
  validations: { count: number };
};

type GetProposedChangesCountsResult = Array<ProposedChangeItem>;

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
