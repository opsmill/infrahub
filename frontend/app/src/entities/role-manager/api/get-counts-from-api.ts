import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export const GET_ROLE_MANAGEMENT_COUNTS = graphql(`
  query GET_ROLE_MANAGEMENT_COUNTS {
    CoreAccountRole {
      count
    }
    CoreAccountGroup {
      count
    }
    CoreGlobalPermission {
      count
    }
    CoreObjectPermission {
      count
    }
    CoreGenericAccount {
      count
    }
  }
`);

export type GetCountsFromApiParams = ContextParams;

export function getCountsFromApi({ branchName, atDate }: GetCountsFromApiParams) {
  return graphqlClient.query({
    query: GET_ROLE_MANAGEMENT_COUNTS,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
