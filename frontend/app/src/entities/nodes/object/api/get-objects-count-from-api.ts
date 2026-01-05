import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

export interface getObjectsCountQueryParams {
  objectKind: string;
  filters?: Array<Filter>;
}

const getObjectsCountQuery = ({ objectKind, filters }: getObjectsCountQueryParams) => {
  const query = {
    query: {
      __name: `GetObjectsCount${objectKind}`,
      [objectKind]: {
        __args: {
          ...(filters ? addFiltersToRequest(filters) : {}),
        },
        count: true,
      },
    },
  };

  return gql(jsonToGraphQLQuery(query));
};

export interface GetObjectsCountFromApiParams extends ContextParams {
  objectKind: string;
  filters?: Array<Filter>;
}

export const getObjectsCountFromApi = async ({
  objectKind,
  filters,
  branchName,
  atDate,
}: GetObjectsCountFromApiParams) => {
  return graphqlClient.query({
    query: getObjectsCountQuery({ objectKind, filters }),
    context: {
      branch: branchName,
      date: atDate,
      queryDeduplication: false,
      processErrorMessage: () => {},
    },
  });
};
