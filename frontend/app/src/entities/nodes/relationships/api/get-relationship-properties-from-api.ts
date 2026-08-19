import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

type GenerateObjectRelationshipsQueryParams = {
  parentKind: string;
  parentId: string;
  relationshipName: string;
  relationshipId: string;
};

const generateRelationshipPropertiesQuery = ({
  parentKind,
  relationshipName,
}: Omit<GenerateObjectRelationshipsQueryParams, "parentId" | "relationshipId">) => {
  const request = {
    query: {
      __name: `Get${parentKind}${relationshipName}RelationshipProperties`,
      __variables: {
        parentIds: "[ID]",
        relationshipIds: "[ID]",
      },
      [parentKind]: {
        __args: {
          ids: new VariableType("parentIds"),
        },
        edges: {
          node: {
            [relationshipName]: {
              __args: {
                ids: new VariableType("relationshipIds"),
              },
              edges: {
                properties: {
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
  parentId,
  relationshipId,
  ...params
}: GetObjectRelationshipsFromApiParams) => {
  const query = gql(generateRelationshipPropertiesQuery(params));

  return graphqlClient.query({
    query,
    variables: { parentIds: [parentId], relationshipIds: [relationshipId] },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
