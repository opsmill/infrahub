import {
  type CheckTaskDetailsFromApiParams,
  checkTaskDetailsFromApi,
} from "@/entities/tasks/api/check-task-details-from-api";

export interface CheckTaskDetailsParams extends CheckTaskDetailsFromApiParams {}

export async function checkTaskDetails(params: CheckTaskDetailsParams): Promise<number> {
  const { data, errors } = await checkTaskDetailsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubTask.count;
}
