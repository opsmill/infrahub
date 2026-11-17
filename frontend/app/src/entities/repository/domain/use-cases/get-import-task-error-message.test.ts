import { beforeEach, describe, expect, it, vi } from "vitest";

import { getImportTaskLogsFromApi } from "@/entities/repository/api/get-import-task-logs-from-api";
import { getImportTaskErrorMessage } from "@/entities/repository/domain/use-cases/get-import-task-error-message";

vi.mock("@/entities/repository/api/get-import-task-logs-from-api");

describe("getImportTaskErrorMessage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns the last error line of the task's log", async () => {
    // GIVEN
    vi.mocked(getImportTaskLogsFromApi).mockResolvedValue([
      { severity: "error", message: "Unable to load the schema" },
      { severity: "info", message: "Importing" },
    ]);

    // WHEN
    const message = await getImportTaskErrorMessage({ taskId: "task-1", logLimit: 10_000 });

    // THEN
    expect(message).toBe("Unable to load the schema");
    expect(getImportTaskLogsFromApi).toHaveBeenCalledWith({
      taskId: "task-1",
      logLimit: 10_000,
    });
  });

  it("returns null when the log has no error line", async () => {
    // GIVEN
    vi.mocked(getImportTaskLogsFromApi).mockResolvedValue([
      { severity: "info", message: "Importing" },
    ]);

    // WHEN / THEN
    await expect(
      getImportTaskErrorMessage({ taskId: "task-1", logLimit: 10_000 })
    ).resolves.toBeNull();
  });

  it("rejects when the api fails, so the failure isn't read as a log with no error line", async () => {
    // GIVEN
    const error = new Error("Network error");
    vi.mocked(getImportTaskLogsFromApi).mockRejectedValue(error);

    // WHEN / THEN
    await expect(getImportTaskErrorMessage({ taskId: "task-1", logLimit: 10_000 })).rejects.toBe(
      error
    );
  });
});
