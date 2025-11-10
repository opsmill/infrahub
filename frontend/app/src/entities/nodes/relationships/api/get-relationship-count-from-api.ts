import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export type getRelationshipCountQueryParams = {
  objectKind: string;
  objectId: string;
  relationshipName: string;
  queryFilter?: string;
};

const getRelationshipCountQuery = ({
  objectKind,
  objectId,
  relationshipName,
  queryFilter,
}: getRelationshipCountQueryParams) => {
  const query = {
    query: {
      __name: `getRelationshipCount_${objectKind}_${relationshipName}`,
      [objectKind]: {
        __args: {
          [queryFilter ?? "ids"]: [objectId],
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
  return graphqlClient.query({
    query: getRelationshipCountQuery(params),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
