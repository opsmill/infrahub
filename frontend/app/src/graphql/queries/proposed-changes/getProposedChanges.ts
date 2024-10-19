import { gql } from "@apollo/client";

export const GET_PROPOSED_CHANGES = gql`
  query GET_PROPOSED_CHANGES($statesVisible: [String], $statesHidden: [String], $search: String) {
    CoreProposedChange(state__values: $statesVisible, any__value: $search, partial_match: true) {
      count
      edges {
        node {
          id
          display_label
          __typename
          _updated_at
          name {
            value
            __typename
          }
          description {
            value
            __typename
          }
          source_branch {
            value
            __typename
          }
          approved_by {
            edges {
              node {
                id
                display_label
                __typename
              }
              __typename
            }
            __typename
          }
          reviewers {
            edges {
              node {
                id
                display_label
                __typename
              }
              __typename
            }
            __typename
          }
          comments {
            count
            __typename
          }
          created_by {
            node {
              id
              display_label
              __typename
            }
            __typename
          }
          validations {
            count
            edges {
              node {
                conclusion {
                  value
                }
              }
            }
          }
        }
        __typename
      }
      permissions {
        edges {
          node {
            kind
            view
            create
            update
            delete
          }
        }
      }
      __typename
    }
    CoreProposedChangeVisible: CoreProposedChange(state__values: $statesVisible) {
      count
    }
    CoreProposedChangeHidden: CoreProposedChange(state__values: $statesHidden) {
      count
    }
  }
`;
