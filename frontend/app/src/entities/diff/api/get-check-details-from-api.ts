import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_CHECK_DETAILS = gql`
  query GET_CHECK_DETAILS($id: ID!) {
    CoreCheck(ids: [$id]) {
      edges {
        node {
          id
          display_label
          name {
            value
          }
          message {
            value
          }
          severity {
            value
          }
          conclusion {
            value
          }
          kind {
            value
          }
          origin {
            value
          }
          created_at {
            value
          }
          ... on CoreDataCheck {
            conflicts {
              value
            }
            keep_branch {
              value
            }
          }
          ... on CoreSchemaCheck {
            conflicts {
              value
            }
          }
          ... on CoreFileCheck {
            files {
              value
            }
            commit {
              value
            }
          }
          ... on CoreArtifactCheck {
            storage_id {
              value
            }
            artifact_id {
              value
            }
          }
          __typename
        }
      }
    }
  }
`;

export interface GetCheckDetailsFromApiParams {
  checkId: string;
}

export const getCheckDetailsFromApi = async ({ checkId }: GetCheckDetailsFromApiParams) => {
  return graphqlClient.query({
    query: GET_CHECK_DETAILS,
    variables: {
      id: checkId,
    },
  });
};
