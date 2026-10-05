import type { BranchContextParams } from "@/shared/api/types";

import {
  getImportTaskLogsFromApi,
  getRepositoryImportTaskFromApi,
} from "@/entities/repository/api/get-repository-import-task-from-api";
import {
  IMPORT_FAILED_TASK_STATES,
  IMPORT_LOG_LIMIT,
  IMPORT_WORKFLOWS,
} from "@/entities/repository/domain/model/repository";
import { getLastErrorLine } from "@/entities/repository/domain/rules/get-last-error-line";

export interface GetRepositoryImportTaskParams extends BranchContextParams {
  repositoryId: string;
}

export function getRepositoryImportTask({
  branchName,
  repositoryId,
}: GetRepositoryImportTaskParams): Promise<string | null> {
  return getRepositoryImportTaskFromApi({
    branch: branchName,
    repositoryId,
    workflows: [...IMPORT_WORKFLOWS],
    states: [...IMPORT_FAILED_TASK_STATES],
  });
}

// Throws when the log can't be fetched, so a failed request isn't mistaken for a log with no error line.
export async function getImportTaskErrorMessage(taskId: string): Promise<string | null> {
  const logs = await getImportTaskLogsFromApi({ taskId, logLimit: IMPORT_LOG_LIMIT });
  return getLastErrorLine(logs);
}
