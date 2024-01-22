import { gql } from "@apollo/client";

export const SEARCH = `
query Search($search: String!) {
  CoreNode (any__value:$search) {
    count
    edges{
      node{
        id
        __typename
      }
    }
  }
}
`;

export const searchQuery = gql(SEARCH);
