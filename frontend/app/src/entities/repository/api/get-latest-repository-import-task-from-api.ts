import {
  graphql,
  graphqlClient,
  type ResultOf,
  type VariablesOf,
} from "@/shared/api/graphql/client";

// The server returns tasks newest first, so `limit: 1` is the latest matching run.
const GET_LATEST_REPOSITORY_IMPORT_TASK = graphql(`
  query GET_LATEST_REPOSITORY_IMPORT_TASK(
    $branch: String!
    $repositoryId: String!
    $workflows: [String]!
    $states: [StateType]!
  ) {
    InfrahubTask(
      branch: $branch
      related_node__ids: [$repositoryId]
      workflow: $workflows
      state: $states
      limit: 1
    ) {
      edges {
        node {
          id
          state
        }
      }
    }
  }
`);

export type GetLatestRepositoryImportTaskFromApiParams = VariablesOf<
  typeof GET_LATEST_REPOSITORY_IMPORT_TASK
>;

type LatestRepositoryImportTaskNode = NonNullable<
  ResultOf<typeof GET_LATEST_REPOSITORY_IMPORT_TASK>["InfrahubTask"]["edges"][number]["node"]
>;

export async function getLatestRepositoryImportTaskFromApi(
  variables: GetLatestRepositoryImportTaskFromApiParams
): Promise<LatestRepositoryImportTaskNode | null> {
  const { data } = await graphqlClient.query({
    query: GET_LATEST_REPOSITORY_IMPORT_TASK,
    variables,
    context: { processErrorMessage: () => {} },
  });
  return data.InfrahubTask.edges[0]?.node ?? null;
}
