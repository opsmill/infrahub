import type { BranchContextParams } from "@/shared/api/types";

import { getLatestRepositoryImportTaskFromApi } from "@/entities/repository/api/get-latest-repository-import-task-from-api";
import type { RepositoryImportTask } from "@/entities/repository/domain/model/branch-repository";
import {
  IMPORT_TASK_STATES,
  IMPORT_WORKFLOWS,
} from "@/entities/repository/domain/model/repository";
import { TASK_STATE_RUNNING } from "@/entities/tasks/domain/model/task";

export interface GetLatestRepositoryImportTaskParams extends BranchContextParams {
  repositoryId: string;
}

export type GetLatestRepositoryImportTaskResult = RepositoryImportTask;

export async function getLatestRepositoryImportTask({
  branchName,
  repositoryId,
}: GetLatestRepositoryImportTaskParams): Promise<GetLatestRepositoryImportTaskResult> {
  const task = await getLatestRepositoryImportTaskFromApi({
    branch: branchName,
    repositoryId,
    workflows: [...IMPORT_WORKFLOWS],
    states: [...IMPORT_TASK_STATES],
  });

  if (!task) return { status: "none" };
  if (task.state === TASK_STATE_RUNNING) return { status: "running" };
  return { status: "failed", taskId: task.id };
}
