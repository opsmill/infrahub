import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const GET_REPOSITORY_IMPORT_TASK = graphql(`
  query GET_REPOSITORY_IMPORT_TASK(
    $branch: String!
    $repositoryId: String!
    $workflows: [String]!
    $limit: Int!
    $logLimit: Int!
  ) {
    InfrahubTask(
      branch: $branch
      related_node__ids: [$repositoryId]
      workflow: $workflows
      limit: $limit
      log_limit: $logLimit
    ) {
      count
      edges {
        node {
          id
          state
          updated_at
          logs {
            edges {
              node {
                message
                severity
                timestamp
              }
            }
          }
        }
      }
    }
  }
`);

export type GetRepositoryImportTaskFromApiParams = VariablesOf<typeof GET_REPOSITORY_IMPORT_TASK>;

export async function getRepositoryImportTaskFromApi(
  variables: GetRepositoryImportTaskFromApiParams
) {
  const { data } = await graphqlClient.query({
    query: GET_REPOSITORY_IMPORT_TASK,
    variables,
  });
  return data.InfrahubTask;
}
