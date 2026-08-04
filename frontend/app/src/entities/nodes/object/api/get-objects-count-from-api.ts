import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

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

  return graphql(jsonToGraphQLQuery(query));
};

export interface GetObjectsCountFromApiParams extends ContextParams {
  objectKind: string;
  filters?: Array<Filter>;
  signal?: AbortSignal;
}

export const getObjectsCountFromApi = async ({
  objectKind,
  filters,
  branchName,
  atDate,
  signal,
}: GetObjectsCountFromApiParams) => {
  return graphqlClient.query({
    query: getObjectsCountQuery({ objectKind, filters }),
    context: {
      branch: branchName,
      date: atDate,
      processErrorMessage: () => {},
      signal,
    },
  });
};
