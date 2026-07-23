import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

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
  relationshipName,
  queryFilter,
}: Omit<getRelationshipCountQueryParams, "objectId">) => {
  const query = {
    query: {
      __name: `getRelationshipCount_${objectKind}_${relationshipName}`,
      __variables: {
        ids: "[ID]",
      },
      [objectKind]: {
        __args: {
          [queryFilter ?? "ids"]: new VariableType("ids"),
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
  objectId,
  ...params
}: GetRelationshipCountFromApiParams) => {
  return graphqlClient.query({
    query: getRelationshipCountQuery(params),
    variables: { ids: [objectId] },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
