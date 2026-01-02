import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import type { NodeMetadata, NodeRelationshipMany } from "@/entities/nodes/types";

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

export interface ProposedChangeDetailsFromApiResponse {
  CoreProposedChange: {
    count: number;
    edges: Array<{
      node_metadata: NodeMetadata;
      node: {
        __typename: "CoreProposedChange";
        id: string;
        display_label: string;
        _updated_at: any | null;
        name: { value: string };
        description: {
          value: string | null;
          updated_at: any | null;
        };
        source_branch: { value: string };
        destination_branch: { value: string };
        state: { value: string };
        is_draft: { value: boolean };
        approved_by: NodeRelationshipMany;
        rejected_by: NodeRelationshipMany;
        reviewers: NodeRelationshipMany;
        comments: { count: number };
      };
    }>;
  };
  InfrahubTask: { count: number };
}

export const getProposedChangeDetailsFromApi = async ({
  proposedChangeId,
}: ProposedChangeDetailsFromApiParams) => {
  return graphqlClient.query<ProposedChangeDetailsFromApiResponse>({
    query: GET_PROPOSED_CHANGE_DETAILS,
    variables: {
      proposedChangeId,
      taskNodeId: proposedChangeId,
    },
  });
};
