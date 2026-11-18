import {
  type CheckTaskDetailsFromApiParams,
  checkTaskDetailsFromApi,
} from "@/entities/tasks/api/check-task-details-from-api";
import type { TaskRequestOptions } from "@/entities/tasks/api/get-task-list-from-api";

export interface CheckTaskDetailsParams extends CheckTaskDetailsFromApiParams {}

export async function checkTaskDetails(
  params: CheckTaskDetailsParams,
  options?: TaskRequestOptions
): Promise<number> {
  const { data, errors } = await checkTaskDetailsFromApi(params, options);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.count;
}
