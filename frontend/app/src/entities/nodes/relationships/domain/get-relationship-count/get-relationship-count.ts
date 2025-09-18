import {
  type GetRelationshipCountFromApiParams,
  getRelationshipCountFromApi,
} from "@/entities/nodes/relationships/api/get-relationship-count-from-api";
import type { NodeObject } from "@/entities/nodes/types";

export type GetRelationshipCountParams = GetRelationshipCountFromApiParams;

export type GetRelationshipCount = (params: GetRelationshipCountParams) => Promise<number>;

export const getRelationshipCount: GetRelationshipCount = async (params) => {
  const { data, error } = await getRelationshipCountFromApi(params);

  if (error) throw error;

  const { objectKind, objectId, relationshipName } = params;
  const result = data[objectKind]?.edges?.map((edge: { node: NodeObject }) => edge.node) ?? [];

  if (!result || result.length === 0) {
    throw new Error(`Cannot find ${objectKind} with id ${objectId}`);
  }

  return result[0][relationshipName].count;
};
