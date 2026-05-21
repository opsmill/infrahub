import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_OBJECT_THREADS = graphql(`
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

export interface GetDiffThreadFromApiParams {
  proposedChangeId: string;
  objectPath: string;
}

export function getDiffThreadFromApi(params: GetDiffThreadFromApiParams) {
  return graphqlClient.query({
    query: GET_OBJECT_THREADS,
    variables: {
      changeIds: [params.proposedChangeId],
      objectPath: params.objectPath,
    },
    fetchPolicy: "no-cache",
  });
}
