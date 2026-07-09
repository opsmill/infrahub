import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import {
  getRelationshipsFromApi,
  type getRelationshipsFromApiParams,
} from "@/entities/nodes/relationships/api/get-relationships-from-api";

export type GetRelationshipsParams = getRelationshipsFromApiParams;

export type GetRelationships = (params: GetRelationshipsParams) => Promise<NodeCore[]>;

export const getRelationships: GetRelationships = async ({
  branchName,
  atDate,
  limit = DEFAULT_PAGE_SIZE,
  offset,
  peer,
  search,
  filterQuery,
}) => {
  const { data } = await getRelationshipsFromApi({
    peer,
    limit,
    offset,
    search,
    branchName,
    atDate,
    filterQuery,
  });

  const relationshipsData = data[peer];

  return relationshipsData.edges.map(({ node }: { node: NodeCore }) => node);
};
