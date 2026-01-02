import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_CHECK_DETAILS = graphql(`
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
`);

export type GetCheckDetailsFromApiParams = VariablesOf<typeof GET_CHECK_DETAILS>;

export const getCheckDetailsFromApi = async (variables: GetCheckDetailsFromApiParams) => {
  return graphqlClient.query({
    query: GET_CHECK_DETAILS,
    variables,
  });
};
