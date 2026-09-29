import { beforeEach, describe, expect, it, vi } from "vitest";

import { getRepositoryImportTaskFromApi } from "@/entities/repository/api/get-repository-import-task-from-api";
import { IMPORT_LOG_LIMIT, IMPORT_WORKFLOWS } from "@/entities/repository/domain/model/repository";
import { getRepositoryImportError } from "@/entities/repository/domain/use-cases/get-repository-import-error";

vi.mock("@/entities/repository/api/get-repository-import-task-from-api");

type ApiResult = Awaited<ReturnType<typeof getRepositoryImportTaskFromApi>>;

const params = { branchName: "feature", repositoryId: "repo-1" };

function mockTasks(
  nodes: Array<{ id: string; logs: Array<{ severity: string; message: string }> }>
) {
  vi.mocked(getRepositoryImportTaskFromApi).mockResolvedValue({
    count: nodes.length,
    edges: nodes.map(({ id, logs }) => ({
      node: {
        id,
        state: "FAILED",
        updated_at: "2026-09-29T10:00:00Z",
        logs: {
          edges: logs.map((log) => ({ node: { ...log, timestamp: "2026-09-29T10:00:00Z" } })),
        },
      },
    })),
  } as unknown as ApiResult);
}

describe("getRepositoryImportError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("queries the latest import task of the repository on the branch", async () => {
    mockTasks([]);

    await getRepositoryImportError(params);

    expect(getRepositoryImportTaskFromApi).toHaveBeenCalledWith({
      branch: "feature",
      repositoryId: "repo-1",
      workflows: [...IMPORT_WORKFLOWS],
      limit: 1,
      logLimit: IMPORT_LOG_LIMIT,
    });
  });

  it("returns the last error line of the task", async () => {
    mockTasks([
      {
        id: "task-1",
        logs: [
          { severity: "info", message: "Importing" },
          { severity: "error", message: "Unable to load the schema" },
        ],
      },
    ]);

    await expect(getRepositoryImportError(params)).resolves.toEqual({
      status: "found",
      taskId: "task-1",
      message: "Unable to load the schema",
    });
  });

  it("keeps the task id when the task has no error line", async () => {
    mockTasks([{ id: "task-1", logs: [{ severity: "info", message: "Importing" }] }]);

    await expect(getRepositoryImportError(params)).resolves.toEqual({
      status: "not-found",
      taskId: "task-1",
    });
  });

  it("returns not-found without a task id when no task matches", async () => {
    mockTasks([]);

    await expect(getRepositoryImportError(params)).resolves.toEqual({
      status: "not-found",
      taskId: null,
    });
  });

  it("returns not-found without a task id when the api fails, and logs the error", async () => {
    const error = new Error("Network error");
    vi.mocked(getRepositoryImportTaskFromApi).mockRejectedValue(error);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    await expect(getRepositoryImportError(params)).resolves.toEqual({
      status: "not-found",
      taskId: null,
    });
    expect(consoleError).toHaveBeenCalledWith(
      expect.stringContaining("repository repo-1 on branch feature"),
      error
    );

    consoleError.mockRestore();
  });
});
