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

// The band stays up whatever happens here: a failed lookup reads as "details not found".
export async function getRepositoryImportTask({
  branchName,
  repositoryId,
}: GetRepositoryImportTaskParams): Promise<string | null> {
  try {
    return await getRepositoryImportTaskFromApi({
      branch: branchName,
      repositoryId,
      workflows: [...IMPORT_WORKFLOWS],
      states: [...IMPORT_FAILED_TASK_STATES],
    });
  } catch (error) {
    console.error(
      `An error occurred while looking up the failed import of repository ${repositoryId} on branch ${branchName}:`,
      error
    );
    return null;
  }
}

export async function getImportTaskErrorMessage(taskId: string): Promise<string | null> {
  try {
    const logs = await getImportTaskLogsFromApi({ taskId, logLimit: IMPORT_LOG_LIMIT });
    return getLastErrorLine(logs);
  } catch (error) {
    console.error(`An error occurred while fetching the log of task ${taskId}:`, error);
    return null;
  }
}
