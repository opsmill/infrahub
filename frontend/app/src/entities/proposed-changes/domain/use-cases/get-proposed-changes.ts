import type { PaginatedResponse } from "@/shared/utils/pagination";

import type { NodeCore, NodeMetadata } from "@/entities/nodes/object/domain/model/node";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import {
  getProposedChangesFromApi,
  type ProposedChangesFromApiParams,
} from "@/entities/proposed-changes/api/get-proposed-changes-from-api";
import { computeProposedChangeSort } from "@/entities/proposed-changes/domain/rules/proposed-change-sort";

export type ProposedChangeNode = {
  id: string;
  display_label: string;
  name: { value: string };
  state: { value: string };
  is_draft: { value: string };
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

// The "visible in list view" selection is a domain rule; the use-case supplies
// it (defaulting to the standard list-view rules) so the api/ fetcher stays pure
// transport and never imports another entity's domain/rules.
export type GetProposedChangesParams = Omit<
  ProposedChangesFromApiParams,
  "getAttributesVisible" | "getRelationshipsVisible"
> &
  Partial<Pick<ProposedChangesFromApiParams, "getAttributesVisible" | "getRelationshipsVisible">>;

export type GetProposedChangesResult = PaginatedResponse<ProposedChangeItem>;

export const getProposedChanges = async ({
  getAttributesVisible = getAttributesVisibleInListView,
  getRelationshipsVisible = getRelationshipsVisibleInListView,
  sort,
  ...params
}: GetProposedChangesParams): Promise<GetProposedChangesResult> => {
  const { data, errors } = await getProposedChangesFromApi({
    ...params,
    sort: computeProposedChangeSort(sort ?? []),
    getAttributesVisible,
    getRelationshipsVisible,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const schemaKindToQuery = params.schema.kind as string;
  const result = data[schemaKindToQuery];

  return {
    items:
      result?.edges?.map((edge: any) => ({
        id: edge.node.id,
        node: edge.node,
        metadata: edge.node_metadata,
      })) ?? [],
    count: result?.count ?? 0,
  };
};
