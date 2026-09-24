import {
  type GetTaskDetailsTitleFromApiParams,
  getTaskDetailsTitleFromApi,
} from "@/entities/tasks/api/get-task-details-title-from-api";
import { WORKFLOW_TYPES } from "@/entities/tasks/domain/model/task";

export type GetTaskDetailsTitleParams = GetTaskDetailsTitleFromApiParams;

export async function getTaskDetailsTitle(params: GetTaskDetailsTitleParams) {
  // A run addressed by its own id must resolve whatever its type is. Without this the query keeps
  // the default namespace-tag scope, which no internal run carries, and the page reports it missing.
  const { data, errors } = await getTaskDetailsTitleFromApi({
    ...params,
    workflowType: params.workflowType ?? [...WORKFLOW_TYPES],
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.edges[0]?.node ?? null;
}
