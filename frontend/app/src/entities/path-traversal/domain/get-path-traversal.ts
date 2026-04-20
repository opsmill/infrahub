import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export type PathNode = {
  id: string;
  kind: string;
  display_label: string;
};

export type PathRelationship = {
  id: string;
  name: string;
  direction: "OUTBOUND" | "INBOUND";
};

export type PathResult = {
  nodes: PathNode[];
  relationships: PathRelationship[];
  depth: number;
};

export type PathTraversalResponse = {
  paths: PathResult[];
  source: PathNode;
  destination: PathNode;
  total_paths_found: number;
};

export type GetPathTraversalParams = {
  sourceId: string;
  destinationId: string;
  maxDepth?: number;
  maxPaths?: number;
  kindFilter?: string[];
  relationshipFilter?: string[];
  excludedKinds?: string[];
  branchName?: string;
  atDate?: Date | string | null;
};

export async function getPathTraversal(
  params: GetPathTraversalParams
): Promise<PathTraversalResponse> {
  const {
    sourceId,
    destinationId,
    maxDepth,
    maxPaths,
    kindFilter,
    relationshipFilter,
    excludedKinds,
    branchName,
    atDate,
  } = params;

  const dataArgs: Record<string, unknown> = {
    source_id: sourceId,
    destination_id: destinationId,
  };

  if (maxDepth !== undefined) dataArgs.max_depth = maxDepth;
  if (maxPaths !== undefined) dataArgs.max_paths = maxPaths;
  if (kindFilter?.length) dataArgs.kind_filter = kindFilter;
  if (relationshipFilter?.length) dataArgs.relationship_filter = relationshipFilter;
  if (excludedKinds?.length) dataArgs.excluded_kinds = excludedKinds;

  const queryObj = {
    query: {
      __name: "GetPathTraversal",
      InfrahubPathTraversal: {
        __args: {
          data: dataArgs,
        },
        paths: {
          nodes: {
            id: true,
            kind: true,
            display_label: true,
          },
          relationships: {
            id: true,
            name: true,
            direction: true,
          },
          depth: true,
        },
        source: {
          id: true,
          kind: true,
          display_label: true,
        },
        destination: {
          id: true,
          kind: true,
          display_label: true,
        },
        total_paths_found: true,
      },
    },
  };

  const queryString = jsonToGraphQLQuery(queryObj);
  const query = gql(queryString);

  const { data, errors } = await graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });

  if (errors && errors.length > 0) {
    throw new Error(errors[0]?.message ?? "Unknown error");
  }

  return data.InfrahubPathTraversal;
}
