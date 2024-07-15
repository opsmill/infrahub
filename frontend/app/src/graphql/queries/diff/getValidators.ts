import { gql } from "@apollo/client";

export const GET_VALIDATORS = gql`
  query GetCoreValidator($ids: [ID]!) {
    CoreValidator(proposed_change__ids: $ids) {
      edges {
        node {
          id
          display_label
          conclusion {
            value
          }
          started_at {
            value
          }
          completed_at {
            value
          }
          state {
            value
          }
          checks {
            edges {
              node {
                conclusion {
                  value
                }
                severity {
                  value
                }
              }
            }
          }
          __typename
        }
      }
    }
  }
`;
