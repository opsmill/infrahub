import {
  type GetObjectAncestorsFromApiParams,
  getObjectAncestorsFromApi,
} from "@/entities/nodes/hierarchy/api/get-object-ancestors-from-api";
import type { NodeCoreWithParent, NodeObject, NodeRelationshipMany } from "@/entities/nodes/types";

export interface GetObjectAncestorsParams extends GetObjectAncestorsFromApiParams {}

export type GetObjectAncestors = (
  params: GetObjectAncestorsParams
) => Promise<Array<NodeCoreWithParent>>;

export const getObjectAncestors: GetObjectAncestors = async ({
  branchName,
  atDate,
  objectKind,
  objectId,
}) => {
  const { data, errors } = await getObjectAncestorsFromApi({
    branchName,
    atDate,
    objectKind,
    objectId,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const result = data[objectKind]?.edges?.map((edge: { node: NodeObject }) => edge.node)?.[0] as
    | (NodeCoreWithParent & { ancestors: NodeRelationshipMany })
    | undefined;

  if (!result) {
    throw new Error(`Cannot find ${objectKind} with id ${objectId}`);
  }

  const { ancestors, ...currentObject } = result;

  return [...ancestors.edges.map((edge) => edge.node), currentObject] as Array<NodeCoreWithParent>;
};
