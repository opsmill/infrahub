import type { BranchContextParams } from "@/shared/api/types";

import {
  getImportTaskLogsFromApi,
  getRepositoryImportTaskFromApi,
} from "@/entities/repository/api/get-repository-import-task-from-api";
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

// While an import is still running, an older failed run isn't the one that set the status, so
// nothing is returned yet and the caller looks again.
export async function getRepositoryImportTask({
  branchName,
  repositoryId,
}: GetRepositoryImportTaskParams): Promise<string | null> {
  const lookup = { branch: branchName, repositoryId, workflows: [...IMPORT_WORKFLOWS] };
  const activeTaskId = await getRepositoryImportTaskFromApi({
    ...lookup,
    states: [...IMPORT_ACTIVE_TASK_STATES],
  });
  if (activeTaskId) return null;

  return getRepositoryImportTaskFromApi({ ...lookup, states: [...IMPORT_FAILED_TASK_STATES] });
}

// Throws when the log can't be fetched, so a failed request isn't mistaken for a log with no error line.
export async function getImportTaskErrorMessage(taskId: string): Promise<string | null> {
  const logs = await getImportTaskLogsFromApi({ taskId, logLimit: IMPORT_LOG_LIMIT });
  return getLastErrorLine(logs);
}
