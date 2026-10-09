import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const REPOSITORY_DELIVERY_STATE = graphql(`
  query REPOSITORY_DELIVERY_STATE($repositoryId: ID!) {
    CoreRepository(ids: [$repositoryId]) {
      edges {
        node {
          id
          delivery_status {
            value
            label
            color
          }
          delivery_failure_cause {
            value
            label
          }
          delivery_error {
            value
          }
          delivery_queue {
            value
          }
        }
      }
    }
  }
`);

export interface GetDeliveryStateFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof REPOSITORY_DELIVERY_STATE> {}

export const getDeliveryStateFromApi = async ({
  repositoryId,
  branchName,
}: GetDeliveryStateFromApiParams) => {
  return graphqlClient.query({
    query: REPOSITORY_DELIVERY_STATE,
    variables: {
      repositoryId,
    },
    context: { branch: branchName },
  });
};
