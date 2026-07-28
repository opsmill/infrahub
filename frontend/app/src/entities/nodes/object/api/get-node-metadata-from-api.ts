import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { nodeMetadataFragment } from "@/shared/api/graphql/fragments";
import type { ContextParams } from "@/shared/api/types";

export interface GetNodeMetadataQueryParams {
  objectId: string;
  objectKind: string;
}

const getNodeMetadataQuery = ({ objectId, objectKind }: GetNodeMetadataQueryParams) => {
  const query = {
    query: {
      __name: `GetNodeMetadata${objectKind}`,
      [objectKind]: {
        __args: {
          ids: [objectId],
        },
        edges: nodeMetadataFragment,
      },
    },
  };

  return graphql(jsonToGraphQLQuery(query));
};

export interface GetNodeMetadataFromApiParams extends ContextParams {
  objectId: string;
  objectKind: string;
}

export const getNodeMetadataFromApi = async ({
  objectId,
  objectKind,
  branchName,
  atDate,
}: GetNodeMetadataFromApiParams) => {
  return graphqlClient.query({
    query: getNodeMetadataQuery({ objectId, objectKind }),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
