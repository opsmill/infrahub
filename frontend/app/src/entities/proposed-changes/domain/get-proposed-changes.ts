import type { NodeCore, NodeMetadata } from "@/entities/nodes/types";
import {
  getProposedChangesFromApi,
  type ProposedChangesFromApiParams,
} from "@/entities/proposed-changes/api/get-proposed-changes-from-api";

export type ProposedChangeNode = {
  id: string;
  display_label: string;
  name: { value: string };
  state: { value: string };
  is_draft: { value: string };
  _updated_at: string;
  source_branch: { value: string };
  approved_by: { edges: Array<{ node: NodeCore }> };
  total_comments: { value: number };
  validations: { count: number };
};

export type ProposedChangeItem = {
  id: string;
  node: ProposedChangeNode;
  metadata: NodeMetadata;
};

export type GetProposedChangesParams = ProposedChangesFromApiParams;

export type GetProposedChangesResult = Array<ProposedChangeItem>;

export type GetProposedChanges = (
  params: GetProposedChangesParams
) => Promise<GetProposedChangesResult>;

export const getProposedChanges: GetProposedChanges = async (params) => {
  const { data, errors } = await getProposedChangesFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const schemaKindToQuery = params.schema.kind as string;

  return (
    data[schemaKindToQuery]?.edges?.map((edge: any) => ({
      id: edge.node.id,
      node: edge.node,
      metadata: edge.node_metadata,
    })) ?? []
  );
};
