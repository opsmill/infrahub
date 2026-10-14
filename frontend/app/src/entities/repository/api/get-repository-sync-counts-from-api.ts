import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";

import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_ERROR_IMPORT_FILTER,
} from "@/entities/repository/domain/model/repository";

export const getRepositorySyncCountsFromApi = async ({ branchName, atDate }: ContextParams) => {
  const query = graphql(
    jsonToGraphQLQuery({
      query: {
        __name: "GetRepositorySyncCounts",
        total: {
          __aliasFor: GENERIC_REPOSITORY_KIND,
          count: true,
        },
        failing: {
          __aliasFor: GENERIC_REPOSITORY_KIND,
          __args: addFiltersToRequest([REPOSITORY_ERROR_IMPORT_FILTER]),
          count: true,
        },
      },
    })
  );

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
      processErrorMessage: () => {},
    },
  });
};
