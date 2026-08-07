import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const RESOLVE_CONFLICT = graphql(`
  mutation RESOLVE_CONFLICT($id: String, $selection: ConflictSelection) {
    ResolveDiffConflict(data: { conflict_id: $id, selected_branch: $selection }) {
      ok
    }
  }
`);

export type ResolveConflictFromApiParams = VariablesOf<typeof RESOLVE_CONFLICT>;

export const resolveConflictFromApi = async ({ id, selection }: ResolveConflictFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RESOLVE_CONFLICT,
    variables: {
      id,
      selection,
    },
  });
};
