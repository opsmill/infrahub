import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_NUMBER_POOL_DIVISIONS = graphql(`
  query GET_NUMBER_POOL_DIVISIONS($poolId: String!) {
    InfrahubNumberPoolDivisions(pool_id: $poolId) {
      allocation_scope {
        id
        name
      }
      divisions {
        display_label
        entries {
          path
          value
          display_label
          peer_kind
        }
        figures {
          size
          used
          used_default_branch
          used_branches
          utilization
        }
      }
    }
  }
`);

export type NumberPoolDivisionsResponse = ResultOf<typeof GET_NUMBER_POOL_DIVISIONS>;

export type NumberPoolDivisionsNode = NumberPoolDivisionsResponse["InfrahubNumberPoolDivisions"];

export type NumberPoolDivisionNode = NumberPoolDivisionsNode["divisions"][number];

export type NumberPoolDivisionEntryNode = NumberPoolDivisionNode["entries"][number];

export interface GetNumberPoolDivisionsFromApiParams extends ContextParams {
  poolId: string;
}

export function getNumberPoolDivisionsFromApi({
  poolId,
  branchName,
  atDate,
}: GetNumberPoolDivisionsFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOL_DIVISIONS,
    variables: { poolId },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
