import { gql } from "@apollo/client";

import {
  Get_Check_DetailsQueryVariables,
  Get_Core_ValidatorsQuery,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_VALIDATORS = gql`
  query GET_CORE_VALIDATORS($id: ID!) {
    CoreValidator(proposed_change__ids: [$id]) {
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

export interface GetValidatorsFromApiParams extends Get_Check_DetailsQueryVariables {}

export const getValidatorsFromApi = async (variables: GetValidatorsFromApiParams) => {
  return graphqlClient.query<Get_Core_ValidatorsQuery, Get_Check_DetailsQueryVariables>({
    query: GET_VALIDATORS,
    variables,
  });
};
