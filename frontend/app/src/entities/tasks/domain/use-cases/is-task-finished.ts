import { TASK_FINAL_STATES } from "@/entities/tasks/domain/model/task";
import { checkTaskDetails } from "@/entities/tasks/domain/use-cases/check-task-details";

export interface IsTaskFinishedParams {
  taskId: string;
}

// A task the server does not list yet reads as not finished, so a caller keeps waiting for it.
export async function isTaskFinished({ taskId }: IsTaskFinishedParams): Promise<boolean> {
  const count = await checkTaskDetails(
    { ids: [taskId], state: TASK_FINAL_STATES },
    { silenceErrors: true }
  );

  return count > 0;
}
