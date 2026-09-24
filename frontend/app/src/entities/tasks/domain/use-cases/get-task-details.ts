import {
  type GetTaskDetailsFromApiParams,
  getTaskDetailsFromApi,
} from "@/entities/tasks/api/get-task-details-from-api";
import { WORKFLOW_TYPES } from "@/entities/tasks/domain/model/task";

export type GetTaskDetailsParams = GetTaskDetailsFromApiParams;

/**
 * A run addressed by its own id must resolve whatever its type is. Left alone the query keeps the
 * default namespace-tag scope, which no internal run carries, and the detail page reports it
 * missing. Listing queries — those with no `ids` — keep today's scope.
 */
function withEveryTypeWhenLookingUpById(
  params?: GetTaskDetailsParams
): GetTaskDetailsParams | undefined {
  if (!params?.ids?.length || params.workflowType) return params;

  return { ...params, workflowType: [...WORKFLOW_TYPES] };
}

export async function getTaskDetails(params?: GetTaskDetailsParams) {
  const { data, errors } = await getTaskDetailsFromApi(withEveryTypeWhenLookingUpById(params));

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.edges
    .map(({ node }) => node)
    .filter((node): node is NonNullable<typeof node> => node !== null);
}
