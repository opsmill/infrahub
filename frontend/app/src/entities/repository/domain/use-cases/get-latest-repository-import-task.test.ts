import { beforeEach, describe, expect, it, vi } from "vitest";

import { getLatestRepositoryImportTaskFromApi } from "@/entities/repository/api/get-latest-repository-import-task-from-api";
import { IMPORT_WORKFLOWS } from "@/entities/repository/domain/model/repository";
import { getLatestRepositoryImportTask } from "@/entities/repository/domain/use-cases/get-latest-repository-import-task";

vi.mock("@/entities/repository/api/get-latest-repository-import-task-from-api");

const params = { branchName: "feature", repositoryId: "repo-1" };

describe("getLatestRepositoryImportTask", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("asks once for the repository's newest running, failed or crashed import on the branch", async () => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTaskFromApi).mockResolvedValue(null);

    // WHEN
    await getLatestRepositoryImportTask(params);

    // THEN
    expect(getLatestRepositoryImportTaskFromApi).toHaveBeenCalledTimes(1);
    expect(getLatestRepositoryImportTaskFromApi).toHaveBeenCalledWith({
      branch: "feature",
      repositoryId: "repo-1",
      workflows: [...IMPORT_WORKFLOWS],
      states: ["RUNNING", "FAILED", "CRASHED"],
    });
  });

  it("reports a running import, so an older failed run isn't picked", async () => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTaskFromApi).mockResolvedValue({
      id: "task-2",
      state: "RUNNING",
    });

    // WHEN / THEN
    await expect(getLatestRepositoryImportTask(params)).resolves.toEqual({ status: "running" });
  });

  it.each(["FAILED", "CRASHED"] as const)("reports a %s import with its task id", async (state) => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTaskFromApi).mockResolvedValue({ id: "task-1", state });

    // WHEN / THEN
    await expect(getLatestRepositoryImportTask(params)).resolves.toEqual({
      status: "failed",
      taskId: "task-1",
    });
  });

  it("reports none when no import matches", async () => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTaskFromApi).mockResolvedValue(null);

    // WHEN / THEN
    await expect(getLatestRepositoryImportTask(params)).resolves.toEqual({ status: "none" });
  });

  it("rejects when the api fails, so the query can tell a failure from no match", async () => {
    // GIVEN
    const error = new Error("Network error");
    vi.mocked(getLatestRepositoryImportTaskFromApi).mockRejectedValue(error);

    // WHEN / THEN
    await expect(getLatestRepositoryImportTask(params)).rejects.toBe(error);
  });
});
