import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_POOL_UTILIZATION = graphql(`
  query GET_POOL_UTILIZATION($poolId: String!) {
    InfrahubResourcePoolUtilization(pool_id: $poolId) {
      edges {
        node {
          id
          display_label
          kind
          weight
          utilization
          utilization_branches
          utilization_default_branch
        }
      }
      count
      utilization
      utilization_branches
      utilization_default_branch
    }
  }
`);

type QueryVariables = VariablesOf<typeof GET_POOL_UTILIZATION>;

export interface GetPoolUtilizationFromApiParams extends QueryVariables {}

export function getPoolUtilizationFromApi({ poolId }: GetPoolUtilizationFromApiParams) {
  return graphqlClient.query({
    query: GET_POOL_UTILIZATION,
    variables: {
      poolId,
    } satisfies QueryVariables,
  });
}
