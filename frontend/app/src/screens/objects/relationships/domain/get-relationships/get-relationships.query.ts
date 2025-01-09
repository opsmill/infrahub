import { getCurrentBranchName } from "@/screens/branches/get-current-branch";
import {
  GetRelationshipsParams,
  RELATIONSHIPS_PER_PAGE,
  getRelationships,
} from "@/screens/objects/relationships/domain/get-relationships/get-relationships";
import { store } from "@/state";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { infiniteQueryOptions } from "@tanstack/react-query";

export function relationshipsInfiniteQueryOptions({
  peer,
  search,
  parentId,
}: GetRelationshipsParams) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return infiniteQueryOptions({
    queryKey: [currentBranchName, timeMachineDate, "relationships", peer, search, parentId],
    queryFn: ({ pageParam }) => getRelationships({ peer, offset: pageParam, search, parentId }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < RELATIONSHIPS_PER_PAGE) {
        return undefined;
      }
      return lastPageParam + RELATIONSHIPS_PER_PAGE;
    },
  });
}
