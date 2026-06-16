import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_THREAD = graphql(`
  query GetCoreThread($ids: [ID]) {
    CoreThread(ids: $ids) {
      edges {
        node {
          id
          display_label
          label {
            value
          }
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
          ... on CoreArtifactThread {
            storage_id {
              value
            }
            artifact_id {
              value
            }
            line_number {
              value
            }
          }
          ... on CoreObjectThread {
            object_path {
              value
            }
          }
          ... on CoreFileThread {
            file {
              value
            }
            line_number {
              value
            }
            commit {
              value
            }
          }
        }
      }
    }
  }
`);

export interface ProposedChangeThreadFromApiParams {
  threadId: string;
}

export const getProposedChangeThreadFromApi = async ({
  threadId,
}: ProposedChangeThreadFromApiParams) => {
  return graphqlClient.query({
    query: GET_THREAD,
    variables: {
      ids: [threadId],
    },
  });
};
