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
    // The form shows the refusal inline, so the global toast is suppressed to avoid a second message.
    context: {
      branch: branchName,
      processErrorMessage: () => {},
    },
  });
}
