import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

import type { NodeCore, NodeObject, NodeRelationshipOne } from "@/entities/nodes/types";

import { buildGetAncestorsQuery } from "../api/get-ip-prefix-ancestors-from-api";

export interface IPPrefixNode extends NodeCore {
  parent?: NodeRelationshipOne;
}

export interface GetIpPrefixAncestorsParams extends ContextParams {
  objectKind: string;
  objectId: string;
}

export type GetIpPrefixAncestors = (params: GetIpPrefixAncestorsParams) => Promise<IPPrefixNode[]>;

export const getIpPrefixAncestors: GetIpPrefixAncestors = async ({
  objectKind,
  objectId,
  atDate,
  branchName,
}) => {
  const query = buildGetAncestorsQuery(objectKind, objectId);

  const { data } = await graphqlClient.query({
    query: gql(query),
    context: {
      branch: branchName,
      date: atDate,
    },
  });

  const result = data[objectKind]?.edges?.map((edge: { node: NodeObject }) => edge.node) ?? [];

  if (!result || result.length === 0) {
    throw new Error(`Cannot find ${objectKind} with id ${objectId}`);
  }

  const { ancestors, ...currentObject } = result[0];
  return [
    currentObject as IPPrefixNode,
    ...(ancestors?.edges?.map((edge: { node: NodeObject }) => edge.node) ?? []),
  ];
};
