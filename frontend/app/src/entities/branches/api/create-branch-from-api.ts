import { gql } from "@apollo/client";

import type {
  Branch_CreateMutation,
  Branch_CreateMutationVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const BRANCH_CREATE = gql`
  mutation BRANCH_CREATE($name: String!, $description: String, $sync_with_git: Boolean) {
    BranchCreate(data: { name: $name, description: $description, sync_with_git: $sync_with_git }) {
      object {
        id
        name
        description
        origin_branch
        branched_from
        created_at
        sync_with_git
        is_default
        status
        has_schema_changes
      }
    }
  }
`;

export interface CreateBranchFromApiParams {
  name: string;
  description?: string | null;
  sync_with_git?: boolean;
}

export function createBranchFromApi(params: CreateBranchFromApiParams) {
  return graphqlClient.mutate<Branch_CreateMutation, Branch_CreateMutationVariables>({
    mutation: BRANCH_CREATE,
    variables: params,
  });
}
