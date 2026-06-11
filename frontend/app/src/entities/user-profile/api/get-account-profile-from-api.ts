import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_ACCOUNT_PROFILE = graphql(`
  query GetAccountProfile {
    AccountProfile {
      id
      display_label
      is_externally_managed
      name {
        value
      }
      label {
        value
      }
      description {
        value
      }
    }
  }
`);

export const getAccountProfileFromApi = async () => {
  return graphqlClient.query({
    query: GET_ACCOUNT_PROFILE,
  });
};
