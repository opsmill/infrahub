import { getImportTaskLogsFromApi } from "@/entities/repository/api/get-import-task-logs-from-api";
import { getLastErrorLine } from "@/entities/repository/domain/rules/get-last-error-line";

export interface GetImportTaskErrorMessageParams {
  taskId: string;
  logLimit: number;
}

export type GetImportTaskErrorMessageResult = string | null;

// Throws when the log can't be fetched, so a failed request isn't mistaken for a log with no error line.
export async function getImportTaskErrorMessage({
  taskId,
  logLimit,
}: GetImportTaskErrorMessageParams): Promise<GetImportTaskErrorMessageResult> {
  const logs = await getImportTaskLogsFromApi({ taskId, logLimit });
  return getLastErrorLine(logs);
}
