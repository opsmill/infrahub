import {
  graphql,
  graphqlClient,
  type ResultOf,
  type VariablesOf,
} from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const REPOSITORY_ACTIVITY = graphql(`
  query REPOSITORY_ACTIVITY($id: String!) {
    InfrahubRepositoryActivity(id: $id) {
      repository_id
      active_runs {
        edges {
          node {
            run_id
            operation
            phase
            branch_name
            worker_id
            started_at
            updated_at
          }
        }
      }
      last_runs {
        edges {
          node {
            operation
            started_at
            finished_at
            branches {
              edges {
                node {
                  branch_name
                  outcome
                }
              }
            }
          }
        }
      }
      lock {
        worker_id
        requested_at
      }
    }
  }
`);

export type RepositoryActivityWire = ResultOf<
  typeof REPOSITORY_ACTIVITY
>["InfrahubRepositoryActivity"];

export interface GetRepositoryActivityFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof REPOSITORY_ACTIVITY> {}

export function getRepositoryActivityFromApi({
  id,
  branchName,
}: GetRepositoryActivityFromApiParams) {
  return graphqlClient.query({
    query: REPOSITORY_ACTIVITY,
    variables: { id },
    context: {
      // A repository that exists only on a feature branch is found only on that branch.
      branch: branchName,
      // The card renders a failed poll in place, and a toast every poll would repeat it.
      processErrorMessage: () => {},
    },
  });
}
