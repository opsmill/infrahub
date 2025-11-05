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

  // Build an ordered list from root (parent = null) to current object
  const allNodes = [...ancestorNodes, currentObject] as Array<NodeCoreWithParent>;
  const nodeMap = new Map(allNodes.map((node) => [node.id, node]));

  // Start from the root (parent is null) and build the ordered chain
  const orderedNodes: Array<NodeCoreWithParent> = [];
  const root = allNodes.find((node) => !node.parent?.node?.id);

  if (root) {
    let current: NodeCoreWithParent | undefined = root;
    while (current) {
      orderedNodes.push(current);
      const nextId = allNodes.find((node) => node.parent?.node?.id === current?.id)?.id;
      current = nextId ? nodeMap.get(nextId) : undefined;
    }
  }

  return orderedNodes;
};
