import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_PROPOSED_CHANGE_DETAILS = graphql(`
  query GET_PROPOSED_CHANGE_DETAILS($proposedChangeId: ID, $taskNodeId: String) {
    CoreProposedChange(ids: [$proposedChangeId]) {
      count
      edges {
        node_metadata {
          created_at
          created_by {
            id
            hfid
            display_label
            __typename
          }
          updated_at
          updated_by {
            id
            hfid
            display_label
            __typename
          }
        }
        node {
          id
          display_label
          __typename
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
          comments {
            count
          }
        }
      }
    }
    InfrahubTask(related_node__ids: [$taskNodeId]) {
      count
    }
  }
`);

export interface ProposedChangeDetailsFromApiParams {
  proposedChangeId: string;
}

export const getProposedChangeDetailsFromApi = async ({
  proposedChangeId,
}: ProposedChangeDetailsFromApiParams) => {
  return graphqlClient.query({
    query: GET_PROPOSED_CHANGE_DETAILS,
    variables: {
      proposedChangeId,
      taskNodeId: proposedChangeId,
    },
  });
};
