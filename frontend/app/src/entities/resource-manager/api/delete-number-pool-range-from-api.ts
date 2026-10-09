import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const DELETE_NUMBER_POOL_RANGE = graphql(`
  mutation DELETE_NUMBER_POOL_RANGE($id: String!) {
    CoreNumberPoolRangeDelete(data: { id: $id }) {
      ok
    }
  }
`);

export interface DeleteNumberPoolRangeFromApiParams extends BranchContextParams {
  id: string;
}

export function deleteNumberPoolRangeFromApi({
  id,
  branchName,
}: DeleteNumberPoolRangeFromApiParams) {
  return graphqlClient.mutate({
    mutation: DELETE_NUMBER_POOL_RANGE,
    variables: { id },
    // Callers display the refusal, so the global toast is suppressed.
    context: {
      branch: branchName,
      processErrorMessage: () => {},
    },
  });
}
