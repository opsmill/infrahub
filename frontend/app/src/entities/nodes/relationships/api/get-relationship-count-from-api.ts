import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export type getRelationshipCountQueryParams = {
  objectKind: string;
  objectId: string;
  relationshipName: string;
  filter?: string;
};

const getRelationshipCountQuery = ({
  objectKind,
  objectId,
  relationshipName,
  filter,
}: getRelationshipCountQueryParams) => {
  console.log("filter: ", filter);
  const query = {
    query: {
      __name: `getRelationshipCount_${objectKind}_${relationshipName}`,
      [objectKind]: {
        __args: {
          [filter ?? "ids"]: [objectId],
        },
        edges: {
          node: {
            [relationshipName]: {
              count: true,
            },
          },
        },
      },
    },
  };

  return gql(jsonToGraphQLQuery(query));
};

export interface GetRelationshipCountFromApiParams
  extends ContextParams,
    getRelationshipCountQueryParams {}

export const getRelationshipCountFromApi = async ({
  branchName,
  atDate,
  ...params
}: GetRelationshipCountFromApiParams) => {
  console.log("params: ", params);
  return graphqlClient.query({
    query: getRelationshipCountQuery(params),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
