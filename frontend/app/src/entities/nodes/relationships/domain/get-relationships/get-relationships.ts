import { getCurrentBranchName } from "@/entities/branches/get-current-branch";
import { getRelationshipsFromApi } from "@/entities/nodes/relationships/api/queries";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const RELATIONSHIPS_PER_PAGE = 20;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetRelationshipsParams = {
  peer: string;
  search?: string;
  parentId?: string;
};

export type GetRelationships = (
  params: GetRelationshipsParams & { limit?: number; offset?: number }
) => Promise<Array<RelationshipNode>>;

export const getRelationships: GetRelationships = async ({ peer, offset, search, parentId }) => {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  const { data } = await getRelationshipsFromApi({
    peer,
    limit: RELATIONSHIPS_PER_PAGE,
    offset,
    search,
    branchName: currentBranchName,
    atDate: timeMachineDate,
    parent: parentId ? { name: "parent", value: parentId } : undefined,
  });

  const relationshipsData = data[peer];

  return relationshipsData.edges.map(({ node }: { node: any }) => ({
    id: node.id,
    display_label: node.display_label,
    __typename: node.__typename,
  }));
};
