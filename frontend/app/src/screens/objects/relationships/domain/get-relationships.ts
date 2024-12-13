import { getCurrentBranchName } from "@/screens/branches/get-currench-branch";
import { getRelationshipsFromApi } from "@/screens/objects/relationships/api/queries";
import { RelationshipNode } from "@/screens/objects/relationships/domain/types";
import { store } from "@/state";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { infiniteQueryOptions } from "@tanstack/react-query";

type GetRelationshipsParams = {
  peer: string;
  search?: string;
};

export type GetRelationships = (
  params: GetRelationshipsParams & { limit?: number; offset?: number }
) => Promise<Array<RelationshipNode>>;

const RELATIONSHIPS_PER_PAGE = 20;

export const getRelationships: GetRelationships = async ({ peer, offset, search }) => {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  const { data } = await getRelationshipsFromApi({
    peer,
    limit: RELATIONSHIPS_PER_PAGE,
    offset,
    search,
    branchName: currentBranchName,
    atDate: timeMachineDate,
  });

  const relationshipsData = data[peer];

  return relationshipsData.edges.map(({ node }: { node: any }) => ({
    id: node.id,
    display_label: node.display_label,
    __typename: node.__typename,
  }));
};

export function relationshipsInfiniteQueryOptions({ peer, search }: GetRelationshipsParams) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return infiniteQueryOptions({
    queryKey: [currentBranchName, timeMachineDate, "relationships", peer, search],
    queryFn: ({ pageParam }) => getRelationships({ peer, offset: pageParam, search: search }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < RELATIONSHIPS_PER_PAGE) {
        return undefined;
      }
      return lastPageParam + RELATIONSHIPS_PER_PAGE;
    },
  });
}
