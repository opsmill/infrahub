import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_OBJECT_THREAD_COMMENTS = graphql(`
  query GET_OBJECT_THREAD_COMMENTS($changeIds: [ID!], $objectPath: String) {
    CoreObjectThread(change__ids: $changeIds, object_path__value: $objectPath) {
      count
      edges {
        node {
          __typename
          id
          display_label
          resolved {
            value
          }
          comments {
            count
            edges {
              node_metadata {
                created_at
                created_by {
                  display_label
                }
              }
              node {
                id
                display_label
                text {
                  value
                }
              }
            }
          }
        }
      }
    }
  }
`);

export interface GetDiffCommentsFromApiParams {
  proposedChangeId: string;
  objectPath: string;
}

export function getDiffCommentsFromApi(params: GetDiffCommentsFromApiParams) {
  return graphqlClient.query({
    query: GET_OBJECT_THREAD_COMMENTS,
    variables: {
      changeIds: [params.proposedChangeId],
      objectPath: params.objectPath,
    },
    fetchPolicy: "no-cache",
  });
}
