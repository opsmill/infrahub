import { gql } from "@apollo/client";

import type {
  Get_Check_DetailsQuery,
  Get_Check_DetailsQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
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

export interface GetCheckDetailsFromApiParams extends Get_Check_DetailsQueryVariables {}

export const getCheckDetailsFromApi = async (variables: GetCheckDetailsFromApiParams) => {
  return graphqlClient.query<Get_Check_DetailsQuery, Get_Check_DetailsQueryVariables>({
    query: GET_CHECK_DETAILS,
    variables,
  });
};
