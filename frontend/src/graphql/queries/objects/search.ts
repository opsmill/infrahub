import { gql } from "@apollo/client";

export const SEARCH = gql`
  query Search($search: String!) {
    CoreNode(any__value: $search, limit: 10) {
      count
      edges {
        node {
          id
          __typename
        }
      }
    }
  }
`;
