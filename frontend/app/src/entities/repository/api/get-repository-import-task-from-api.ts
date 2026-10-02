import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const GET_REPOSITORY_FAILED_IMPORT_TASK = graphql(`
  query GET_REPOSITORY_FAILED_IMPORT_TASK(
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
        }
      }
    }
  }
`);

export type GetRepositoryImportTaskFromApiParams = VariablesOf<
  typeof GET_REPOSITORY_FAILED_IMPORT_TASK
>;

export async function getRepositoryImportTaskFromApi(
  variables: GetRepositoryImportTaskFromApiParams
): Promise<string | null> {
  const { data } = await graphqlClient.query({
    query: GET_REPOSITORY_FAILED_IMPORT_TASK,
    variables,
  });
  return data.InfrahubTask.edges[0]?.node?.id ?? null;
}

const GET_IMPORT_TASK_LOGS = graphql(`
  query GET_IMPORT_TASK_LOGS($taskId: String!, $logLimit: Int!) {
    InfrahubTask(ids: [$taskId], log_limit: $logLimit) {
      edges {
        node {
          logs {
            edges {
              node {
                message
                severity
              }
            }
          }
        }
      }
    }
  }
`);

export type GetImportTaskLogsFromApiParams = VariablesOf<typeof GET_IMPORT_TASK_LOGS>;

export async function getImportTaskLogsFromApi(variables: GetImportTaskLogsFromApiParams) {
  const { data } = await graphqlClient.query({ query: GET_IMPORT_TASK_LOGS, variables });
  const logs = data.InfrahubTask.edges[0]?.node?.logs?.edges ?? [];
  return logs.flatMap((edge) => (edge?.node ? [edge.node] : []));
}
