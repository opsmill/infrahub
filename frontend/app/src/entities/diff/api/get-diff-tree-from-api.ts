import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

const DIFF_TREE_QUERY = graphql(`
  query GET_DIFF_TREE($branchName: String, $filters: DiffTreeQueryFilters, $limit: Int, $offset: Int) {
    DiffTree(branch: $branchName, filters: $filters, include_parents: true, limit: $limit, offset: $offset) {
      nodes {
        uuid
        relationships {
          label
          status
          contains_conflict
          cardinality
          elements {
            conflict {
              base_branch_label
              base_branch_action
              base_branch_changed_at
              base_branch_value
              diff_branch_label
              diff_branch_action
              diff_branch_changed_at
              diff_branch_value
              selected_branch
              uuid
            }
            last_changed_at
            contains_conflict
            peer_id
            properties {
              conflict {
                base_branch_label
                base_branch_action
                base_branch_changed_at
                base_branch_value
                diff_branch_label
                diff_branch_action
                diff_branch_changed_at
                diff_branch_value
                selected_branch
                uuid
              }
              last_changed_at
              new_value
              previous_value
              property_type
              status
              path_identifier
            }
            status
            path_identifier
            peer_label
          }
          last_changed_at
          name
          path_identifier
        }
        conflict {
          base_branch_label
          base_branch_action
          base_branch_changed_at
          diff_branch_action
          diff_branch_label
          base_branch_value
          diff_branch_changed_at
          diff_branch_value
          selected_branch
          uuid
        }
        attributes {
          contains_conflict
          last_changed_at
          name
          conflict {
            base_branch_label
            base_branch_action
            base_branch_changed_at
            base_branch_value
            diff_branch_label
            diff_branch_action
            diff_branch_changed_at
            diff_branch_value
            selected_branch
            uuid
          }
          properties {
            conflict {
              base_branch_label
              base_branch_action
              base_branch_changed_at
              base_branch_value
              diff_branch_label
              diff_branch_action
              diff_branch_changed_at
              diff_branch_value
              selected_branch
              uuid
            }
            last_changed_at
            new_value
            previous_value
            property_type
            status
            path_identifier
          }
          status
          path_identifier
        }
        kind
        contains_conflict
        label
        last_changed_at
        status
        path_identifier
        parent {
          uuid
          relationship_name
          kind
        }
      }
      to_time
      base_branch
      diff_branch
      from_time
    }
  }
`);

export type GetDiffTreeFromApiParams = PaginationParams & {
  branchName: string;
  filters?: VariablesOf<typeof DIFF_TREE_QUERY>["filters"];
};

export const getDiffTreeFromApi = async ({
  branchName,
  filters,
  limit,
  offset,
}: GetDiffTreeFromApiParams) => {
  return graphqlClient.query({
    query: DIFF_TREE_QUERY,
    variables: {
      branchName,
      filters,
      limit,
      offset,
    } satisfies VariablesOf<typeof DIFF_TREE_QUERY>,
  });
};
