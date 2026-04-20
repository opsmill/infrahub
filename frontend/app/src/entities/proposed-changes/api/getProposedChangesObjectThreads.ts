import { graphql } from "gql.tada";

export const GET_OBJECT_THREADS = graphql(`
  query GET_OBJECT_THREADS($changeIds: [ID!], $objectPath: String) {
    CoreObjectThread(change__ids: $changeIds, object_path__value: $objectPath) {
      count
      edges {
        node {
          __typename
          id
          comments {
            count
          }
        }
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
    }
  }
`);
