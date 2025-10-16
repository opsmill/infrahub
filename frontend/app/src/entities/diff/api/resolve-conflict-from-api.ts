import { gql } from "@apollo/client";

import type { ConflictSelection } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const RESOLVE_CONFLICT = gql`
  mutation RESOLVE_CONFLICT ($id: String, $selection: ConflictSelection) {
    ResolveDiffConflict(data:{conflict_id: $id, selected_branch: $selection}){
      ok
    }
  }
`;

export type ResolveConflictFromApiParams = {
  id: string;
  selection: ConflictSelection | null;
};

export const resolveConflictFromApi = async ({ id, selection }: ResolveConflictFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RESOLVE_CONFLICT,
    variables: {
      id,
      selection,
    },
  });
};
