import { graphql, graphqlClient } from "@/shared/api/graphql/client";

const GET_SERVICE_REQUEST = graphql(`
  query GetServiceRequest($requestId: ID!) {
    CoreServiceRequest(ids: [$requestId]) {
      edges {
        node {
          id
          status {
            value
          }
          message {
            value
          }
          branch {
            value
          }
          entry {
            node {
              id
              name {
                value
              }
            }
          }
          proposed_change {
            node {
              id
            }
          }
          service {
            node {
              id
              __typename
            }
          }
        }
      }
    }
  }
`);

export interface GetServiceRequestFromApiParams {
  requestId: string;
  // The request itself is branch-agnostic; only its `service` relationship lives on the request branch.
  branchName?: string;
}

export const getServiceRequestFromApi = async ({
  requestId,
  branchName,
}: GetServiceRequestFromApiParams) => {
  return graphqlClient.query({
    query: GET_SERVICE_REQUEST,
    variables: { requestId },
    context: branchName ? { branch: branchName } : undefined,
  });
};
