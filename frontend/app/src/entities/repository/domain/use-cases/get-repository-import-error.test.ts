import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getImportTaskLogsFromApi,
  getRepositoryImportTaskFromApi,
} from "@/entities/repository/api/get-repository-import-task-from-api";
import { IMPORT_LOG_LIMIT, IMPORT_WORKFLOWS } from "@/entities/repository/domain/model/repository";
import {
  getImportTaskErrorMessage,
  getRepositoryImportTask,
} from "@/entities/repository/domain/use-cases/get-repository-import-error";

vi.mock("@/entities/repository/api/get-repository-import-task-from-api");

const params = { branchName: "feature", repositoryId: "repo-1" };

describe("getRepositoryImportTask", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("asks for a running import, then for the newest failed or crashed import of the repository on the branch", async () => {
    // GIVEN no import is running
    vi.mocked(getRepositoryImportTaskFromApi)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce("task-1");

    // WHEN
    const lookup = await getRepositoryImportTask(params);

    // THEN
    expect(lookup).toEqual({ status: "failed", taskId: "task-1" });
    expect(getRepositoryImportTaskFromApi).toHaveBeenNthCalledWith(1, {
      branch: "feature",
      repositoryId: "repo-1",
      workflows: [...IMPORT_WORKFLOWS],
      states: ["RUNNING"],
    });
    expect(getRepositoryImportTaskFromApi).toHaveBeenNthCalledWith(2, {
      branch: "feature",
      repositoryId: "repo-1",
      workflows: [...IMPORT_WORKFLOWS],
      states: ["FAILED", "CRASHED"],
    });
  });

  it("reports a running import, so an older failed run isn't picked", async () => {
    // GIVEN
    vi.mocked(getRepositoryImportTaskFromApi).mockResolvedValueOnce("running-task");

    // WHEN
    const lookup = await getRepositoryImportTask(params);

    // THEN
    expect(lookup).toEqual({ status: "running" });
    expect(getRepositoryImportTaskFromApi).toHaveBeenCalledTimes(1);
  });

  it("reports no match when no import is running and no failed import matches", async () => {
    // GIVEN
    vi.mocked(getRepositoryImportTaskFromApi).mockResolvedValue(null);

    // WHEN / THEN
    await expect(getRepositoryImportTask(params)).resolves.toEqual({ status: "not-found" });
  });

  it("rejects when the api fails, so the query can tell a failure from no match", async () => {
    // GIVEN
    const error = new Error("Network error");
    vi.mocked(getRepositoryImportTaskFromApi).mockRejectedValue(error);

    // WHEN / THEN
    await expect(getRepositoryImportTask(params)).rejects.toBe(error);
  });
});

describe("getImportTaskErrorMessage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the last error line of the task's log", async () => {
    // GIVEN
    vi.mocked(getImportTaskLogsFromApi).mockResolvedValue([
      { severity: "error", message: "Unable to load the schema" },
      { severity: "info", message: "Importing" },
    ]);

    // WHEN
    const message = await getImportTaskErrorMessage("task-1");

    // THEN
    expect(message).toBe("Unable to load the schema");
    expect(getImportTaskLogsFromApi).toHaveBeenCalledWith({
      taskId: "task-1",
      logLimit: IMPORT_LOG_LIMIT,
    });
  });

  it("returns null when the log has no error line", async () => {
    // GIVEN
    vi.mocked(getImportTaskLogsFromApi).mockResolvedValue([
      { severity: "info", message: "Importing" },
    ]);

    // WHEN / THEN
    await expect(getImportTaskErrorMessage("task-1")).resolves.toBeNull();
  });

  it("rejects when the api fails, so the failure isn't read as a log with no error line", async () => {
    // GIVEN
    const error = new Error("Network error");
    vi.mocked(getImportTaskLogsFromApi).mockRejectedValue(error);

    // WHEN / THEN
    await expect(getImportTaskErrorMessage("task-1")).rejects.toBe(error);
  });
});
