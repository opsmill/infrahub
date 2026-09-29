import type { BranchContextParams } from "@/shared/api/types";

import { getRepositoryImportTaskFromApi } from "@/entities/repository/api/get-repository-import-task-from-api";
import { IMPORT_LOG_LIMIT, IMPORT_WORKFLOWS } from "@/entities/repository/domain/model/repository";
import { getLastErrorLine } from "@/entities/repository/domain/rules/get-last-error-line";

export interface GetRepositoryImportErrorParams extends BranchContextParams {
  repositoryId: string;
}

export type RepositoryImportError =
  | { status: "found"; taskId: string; message: string }
  | { status: "not-found"; taskId: string | null };

export type GetRepositoryImportError = (
  params: GetRepositoryImportErrorParams
) => Promise<RepositoryImportError>;

// The band stays up whatever happens here: a failed lookup reads as "details not found".
export const getRepositoryImportError: GetRepositoryImportError = async ({
  branchName,
  repositoryId,
}) => {
  try {
    const tasks = await getRepositoryImportTaskFromApi({
      branch: branchName,
      repositoryId,
      workflows: [...IMPORT_WORKFLOWS],
      limit: 1,
      logLimit: IMPORT_LOG_LIMIT,
    });

    const task = tasks.edges[0]?.node;
    if (!task?.id) return { status: "not-found", taskId: null };

    const logs = (task.logs?.edges ?? []).flatMap((edge) => (edge?.node ? [edge.node] : []));
    const message = getLastErrorLine(logs);

    return message === null
      ? { status: "not-found", taskId: task.id }
      : { status: "found", taskId: task.id, message };
  } catch (error) {
    console.error(
      `An error occurred while fetching the import error of repository ${repositoryId} on branch ${branchName}:`,
      error
    );
    return { status: "not-found", taskId: null };
  }
};
