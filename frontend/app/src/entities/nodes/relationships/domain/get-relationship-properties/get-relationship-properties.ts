import {
  GetObjectRelationshipsFromApiParams,
  getRelationshipPropertiesFromApi,
} from "@/entities/nodes/relationships/api/get-relationship-properties-from-api";
import { RelationshipProperties } from "@/entities/nodes/relationships/domain/types";

export type GetRelationshipPropertiesParams = GetObjectRelationshipsFromApiParams;

export type GetRelationshipProperties = (
  params: GetRelationshipPropertiesParams
) => Promise<RelationshipProperties>;

export const getRelationshipProperties: GetRelationshipProperties = async (params) => {
  const { data } = await getRelationshipPropertiesFromApi(params);

  return data[params.parentKind].edges[0].node[params.relationshipName].edges[0].properties;
};
