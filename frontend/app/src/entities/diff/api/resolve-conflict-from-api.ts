import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const RESOLVE_CONFLICT = graphql(`
  mutation RESOLVE_CONFLICT($id: String, $selection: ConflictSelection) {
    ResolveDiffConflict(data: { conflict_id: $id, selected_branch: $selection }) {
      ok
    }
  }
`);

export type ResolveConflictFromApiParams = {
  id: string;
  selection: VariablesOf<typeof RESOLVE_CONFLICT>["selection"];
};

export const resolveConflictFromApi = async ({ id, selection }: ResolveConflictFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RESOLVE_CONFLICT,
    variables: {
      id,
      selection,
    } satisfies VariablesOf<typeof RESOLVE_CONFLICT>,
  });
};
