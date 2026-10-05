import type { BranchContextParams } from "@/shared/api/types";

import {
  getImportTaskLogsFromApi,
  getRepositoryImportTaskFromApi,
} from "@/entities/repository/api/get-repository-import-task-from-api";
import type { RepositoryImportTaskLookup } from "@/entities/repository/domain/model/branch-repository";
import {
  IMPORT_ACTIVE_TASK_STATES,
  IMPORT_FAILED_TASK_STATES,
  IMPORT_LOG_LIMIT,
  IMPORT_WORKFLOWS,
} from "@/entities/repository/domain/model/repository";
import { getLastErrorLine } from "@/entities/repository/domain/rules/get-last-error-line";

export interface GetRepositoryImportTaskParams extends BranchContextParams {
  repositoryId: string;
}

// While an import is still running, an older failed run isn't the one that set the status, so no
// failed run is looked up yet.
export async function getRepositoryImportTask({
  branchName,
  repositoryId,
}: GetRepositoryImportTaskParams): Promise<RepositoryImportTaskLookup> {
  const lookup = { branch: branchName, repositoryId, workflows: [...IMPORT_WORKFLOWS] };
  const activeTaskId = await getRepositoryImportTaskFromApi({
    ...lookup,
    states: [...IMPORT_ACTIVE_TASK_STATES],
  });
  if (activeTaskId) return { status: "running" };

  const failedTaskId = await getRepositoryImportTaskFromApi({
    ...lookup,
    states: [...IMPORT_FAILED_TASK_STATES],
  });
  return failedTaskId ? { status: "failed", taskId: failedTaskId } : { status: "not-found" };
}

// Throws when the log can't be fetched, so a failed request isn't mistaken for a log with no error line.
export async function getImportTaskErrorMessage(taskId: string): Promise<string | null> {
  const logs = await getImportTaskLogsFromApi({ taskId, logLimit: IMPORT_LOG_LIMIT });
  return getLastErrorLine(logs);
}
