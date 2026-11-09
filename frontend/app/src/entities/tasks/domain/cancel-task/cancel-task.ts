import {
  type CancelTaskFromApiParams,
  cancelTaskFromApi,
} from "@/entities/tasks/api/cancel-task-from-api";

export type CancelTaskParams = CancelTaskFromApiParams;

export const cancelTask = async (params: CancelTaskParams): Promise<string | null> => {
  const { data, errors } = await cancelTaskFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((error) => error.message).join("; "));
  }

  return data?.InfrahubTaskCancel?.task?.id ?? null;
};
