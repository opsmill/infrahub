import { gql } from "@apollo/client";

export const SEARCH = gql`
  query Search($search: String!) {
    InfrahubSearchAnywhere(q: $search, limit: 4, partial_match: true) {
      count
      edges {
        node {
          id
          kind
        }
      }
    }
  }
`;
