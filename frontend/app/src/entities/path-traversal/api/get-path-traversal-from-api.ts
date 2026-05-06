import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import type {
  GetPathTraversalParams,
  PathTraversalResponse,
} from "@/entities/path-traversal/domain/path-traversal.types";

const pathFields = {
  objects: {
    __aliasFor: "nodes",
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
};

export async function getPathTraversalFromApi(params: GetPathTraversalParams) {
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

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: "GetPathTraversal",
      InfrahubPathTraversal: {
        __args: { data: dataArgs },
        paths: pathFields,
        source: { id: true, kind: true, display_label: true },
        destination: { id: true, kind: true, display_label: true },
        total_paths_found: true,
      },
    },
  });

  return graphqlClient.query<{ InfrahubPathTraversal: PathTraversalResponse }>({
    query: gql(queryString),
    context: { branch: branchName, date: atDate },
  });
}
