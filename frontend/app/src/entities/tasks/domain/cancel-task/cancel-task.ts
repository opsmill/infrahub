import {
  type CancelTaskFromApiParams,
  cancelTaskFromApi,
} from "@/entities/tasks/api/cancel-task-from-api";

export type CancelTaskParams = CancelTaskFromApiParams;

export interface CancelTaskResult {
  ok: boolean;
  taskId?: string;
}

export const cancelTask = async (params: CancelTaskParams): Promise<CancelTaskResult> => {
  const { data, errors } = await cancelTaskFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (!data?.InfrahubTaskCancel) {
    throw new Error("Failed to cancel the task");
  }

  return {
    ok: data.InfrahubTaskCancel.ok ?? false,
    taskId: data.InfrahubTaskCancel.task?.id ?? undefined,
  };
};
