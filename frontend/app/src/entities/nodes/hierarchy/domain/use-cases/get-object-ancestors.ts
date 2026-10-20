import {
  type GetObjectAncestorsFromApiParams,
  getObjectAncestorsFromApi,
} from "@/entities/nodes/hierarchy/api/get-object-ancestors-from-api";
import type { NodeCoreWithParent, NodeObject } from "@/entities/nodes/object/domain/model/node";

export interface GetObjectAncestorsParams extends GetObjectAncestorsFromApiParams {}

export interface GetObjectAncestorsResult {
  /** From the top-level ancestor (or as far up as the ancestors go) down to the object itself. */
  chain: Array<NodeCoreWithParent>;
  /** Ancestors the chain does not reach, which only happens when an object in it has more than one parent. */
  otherAncestors: Array<NodeCoreWithParent>;
}

export type GetObjectAncestors = (
  params: GetObjectAncestorsParams
) => Promise<GetObjectAncestorsResult>;

interface NodeWithAncestors extends NodeCoreWithParent {
  ancestors?: { edges?: Array<{ node: NodeCoreWithParent | null }> };
}

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
    | NodeWithAncestors
    | undefined;

  if (!result) {
    throw new Error(`Cannot find ${objectKind} with id ${objectId}`);
  }

  const { ancestors, ...currentObject } = result;
  const ancestorNodes = ancestors?.edges?.map((edge) => edge.node).filter((n) => !!n) ?? [];
  const ancestorsById = new Map(ancestorNodes.map((node) => [node.id, node]));

  const chain: Array<NodeCoreWithParent> = [];
  const chainIds = new Set<string>();
  let current: NodeCoreWithParent | undefined = currentObject;

  // Damaged hierarchy data can make the parents loop back, so stop at the first object seen twice.
  while (current && !chainIds.has(current.id)) {
    chain.unshift(current);
    chainIds.add(current.id);
    const parentId: string | undefined = current.parent?.node?.id;
    current = parentId ? ancestorsById.get(parentId) : undefined;
  }

  return {
    chain,
    otherAncestors: ancestorNodes.filter((node) => !chainIds.has(node.id)),
  };
};
