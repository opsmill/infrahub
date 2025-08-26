import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

const GET_THREAD = gql`
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
        ... on  CoreArtifactThread {
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
          object_path{
            value
          }
        }
        ... on CoreFileThread {
          file{
            value
          }
          line_number{
            value
          }
          commit {
            value
          }
        }
      }
    }
  }
}`;

export interface ProposedChangeThreadFromApiParams extends ContextParams {
  threadId: string;
}

export const getProposedChangeThreadFromApi = async ({
  threadId,
  branchName,
  atDate,
}: ProposedChangeThreadFromApiParams) => {
  return graphqlClient.query({
    query: GET_THREAD,
    variables: {
      ids: [threadId],
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
