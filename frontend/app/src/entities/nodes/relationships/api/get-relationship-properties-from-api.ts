import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

type GenerateObjectRelationshipsQueryParams = {
  parentKind: string;
  parentId: string;
  relationshipName: string;
  relationshipId: string;
};

const generateRelationshipPropertiesQuery = ({
  parentKind,
  parentId,
  relationshipName,
  relationshipId,
}: GenerateObjectRelationshipsQueryParams) => {
  const request = {
    query: {
      __name: `Get${parentKind}${relationshipName}RelationshipProperties`,
      [parentKind]: {
        __args: {
          ids: [parentId],
        },
        edges: {
          node: {
            [relationshipName]: {
              __args: {
                ids: [relationshipId],
              },
              edges: {
                properties: {
                  is_visible: true,
                  is_protected: true,
                  updated_at: true,
                  source: {
                    id: true,
                    hfid: true,
                    display_label: true,
                  },
                  owner: {
                    id: true,
                    hfid: true,
                    display_label: true,
                  },
                },
              },
            },
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};

export type GetObjectRelationshipsFromApiParams = GenerateObjectRelationshipsQueryParams & {
  branchName: string;
  atDate: Date | null;
};

export const getRelationshipPropertiesFromApi = ({
  branchName,
  atDate,
  ...params
}: GetObjectRelationshipsFromApiParams) => {
  const query = gql(generateRelationshipPropertiesQuery(params));

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
