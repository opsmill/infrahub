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
          created_by {
            node {
              display_label
            }
          }
          comments {
            count
            edges {
              node {
                id
                display_label
                created_by {
                  node {
                    display_label
                  }
                }
                created_at {
                  value
                }
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
