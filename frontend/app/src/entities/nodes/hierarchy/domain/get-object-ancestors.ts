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
  const ancestorNodes = ancestors?.edges?.map((edge) => edge.node).filter((n) => !!n) ?? [];

  // Build an ordered list from current object to root (or as far up as we can go)
  const allNodes = [...ancestorNodes, currentObject] as Array<NodeCoreWithParent>;
  const nodeMap = new Map(allNodes.map((node) => [node.id, node]));

  const orderedNodes: Array<NodeCoreWithParent> = [];
  let current: NodeCoreWithParent | undefined = currentObject;

  while (current) {
    orderedNodes.unshift(current);
    const parentId: string | undefined = current.parent?.node?.id;
    current = parentId ? nodeMap.get(parentId) : undefined;
  }

  return orderedNodes;
};
