import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

import { BACKEND_MOCK_NUMBER_POOL_ID } from "@/entities/resource-manager/domain/model/number-pool";

const GET_NUMBER_POOL_UTILIZATION = graphql(`
  query GET_NUMBER_POOL_UTILIZATION($poolId: String!) {
    InfrahubNumberPoolUtilization(pool_id: $poolId) {
      figures {
        size
        used
        used_default_branch
        used_branches
        utilization
      }
      ranges {
        id
        start
        end
        weight
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

export type NumberPoolUtilizationResponse = ResultOf<typeof GET_NUMBER_POOL_UTILIZATION>;

export type NumberPoolUtilizationNode =
  NumberPoolUtilizationResponse["InfrahubNumberPoolUtilization"];

export type NumberPoolUtilizationFiguresNode = NumberPoolUtilizationNode["figures"];

export interface GetNumberPoolUtilizationFromApiParams extends ContextParams {
  poolId: string;
}

export function getNumberPoolUtilizationFromApi({
  branchName,
  atDate,
}: GetNumberPoolUtilizationFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOL_UTILIZATION,
    variables: { poolId: BACKEND_MOCK_NUMBER_POOL_ID },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
