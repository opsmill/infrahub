import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import type { PathObject, PathResult } from "./get-path-traversal";

export type ReachableObject = {
  id: string;
  kind: string;
  display_label: string;
  depth: number;
  relationship_name: string;
  path: PathResult;
};

export type ReachableObjectsResponse = {
  source: PathObject;
  reachable_objects: ReachableObject[];
  paths: PathResult[];
  total_found: number;
};

export type GetReachableObjectsParams = {
  sourceId: string;
  targetKinds: string[];
  maxDepth?: number;
  maxResults?: number;
  branchName?: string;
  atDate?: Date | string | null;
};

export async function getReachableObjects(
  params: GetReachableObjectsParams
): Promise<ReachableObjectsResponse> {
  const { sourceId, targetKinds, maxDepth, maxResults, branchName, atDate } = params;

  const dataArgs: Record<string, unknown> = {
    source_id: sourceId,
    target_kinds: targetKinds,
  };
  if (maxDepth !== undefined) dataArgs.max_depth = maxDepth;
  if (maxResults !== undefined) dataArgs.max_results = maxResults;

  const pathFields = {
    objects: {
      __aliasFor: "nodes",
      id: true,
      kind: true,
      display_label: true,
    },
    relationships: { id: true, name: true, direction: true },
    depth: true,
  };

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: "GetReachableObjects",
      InfrahubReachableNodes: {
        __args: { data: dataArgs },
        source: { id: true, kind: true, display_label: true },
        reachable_objects: {
          __aliasFor: "reachable_nodes",
          id: true,
          kind: true,
          display_label: true,
          depth: true,
          relationship_name: true,
          path: pathFields,
        },
        paths: pathFields,
        total_found: true,
      },
    },
  });

  const { data, errors } = await graphqlClient.query({
    query: gql(queryString),
    context: { branch: branchName, date: atDate },
  });

  if (errors && errors.length > 0) {
    throw new Error(errors[0]?.message ?? "Unknown error");
  }

  return data.InfrahubReachableNodes;
}
