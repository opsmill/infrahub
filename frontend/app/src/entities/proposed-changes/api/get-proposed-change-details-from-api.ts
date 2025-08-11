import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

const GET_DETAILS = gql`
  query GET_PROPOSED_CHANGE_DETAILS($id: ID, $nodeId: String, $state: String) {
    CoreProposedChange(ids: [$id], state__value: $state) {
      count
      edges {
        node {
          id
          display_label
          _updated_at
          name {
            value
          }
          description {
            value
            updated_at
          }
          source_branch {
            value
          }
          destination_branch {
            value
          }
          state {
            value
          }
          is_draft {
            value
          }
          approved_by {
            edges {
              node {
                id
                display_label
              }
            }
          }
          rejected_by {
            edges {
              node {
                id
                display_label
              }
            }
          }
          reviewers {
            edges {
              node {
                id
                display_label
              }
            }
          }
          created_by {
            node {
              id
              display_label
            }
          }
          comments {
            count
          }
          created_by {
            node {
              id
              display_label
            }
          }
        }
      }
    }
    InfrahubTask(related_node__ids: [$nodeId]) {
      count
    }
  }
`;

export interface ProposedChangeDetailsFromApiParams extends ContextParams {
  id: string;
  nodeId: string;
  state: string;
}

export const getProposedChangeDetailsFromApi = async ({
  id,
  nodeId,
  state,
  branchName,
  atDate,
}: ProposedChangeDetailsFromApiParams) => {
  return graphqlClient.query({
    query: GET_DETAILS,
    variables: {
      id,
      nodeId,
      state,
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
