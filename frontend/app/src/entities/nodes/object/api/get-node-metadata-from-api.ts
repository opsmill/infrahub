import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
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
        edges: {
          node_metadata: {
            created_at: true,
            created_by: {
              id: true,
              display_label: true,
              hfid: true,
              __typename: true,
            },
            updated_at: true,
            updated_by: {
              id: true,
              display_label: true,
              hfid: true,
              __typename: true,
            },
          },
        },
      },
    },
  };

  return gql(jsonToGraphQLQuery(query));
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
