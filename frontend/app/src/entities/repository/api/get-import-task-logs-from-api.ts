import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

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
  const { data } = await graphqlClient.query({
    query: GET_IMPORT_TASK_LOGS,
    variables,
    context: { processErrorMessage: () => {} },
  });
  const logs = data.InfrahubTask.edges[0]?.node?.logs?.edges ?? [];
  return logs.flatMap((edge) => (edge?.node ? [edge.node] : []));
}
