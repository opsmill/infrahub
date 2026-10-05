import { toast } from "react-toastify";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getImportTaskLogsFromApi,
  getRepositoryImportTaskFromApi,
} from "./get-repository-import-task-from-api";

vi.mock("react-toastify", () => ({ toast: vi.fn() }));

const lookupParams = { branch: "feature", repositoryId: "repo-1", workflows: [], states: [] };

const respondWith = (body: unknown) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    )
  );
};

describe("repository import task fetchers", () => {
  beforeEach(() => {
    vi.mocked(toast).mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("return the id of the task the lookup found", async () => {
    // GIVEN
    respondWith({ data: { InfrahubTask: { edges: [{ node: { id: "task-1" } }] } } });

    // WHEN / THEN
    await expect(getRepositoryImportTaskFromApi(lookupParams)).resolves.toBe("task-1");
  });

  it("reject a failed task lookup without showing the error toast", async () => {
    // GIVEN
    respondWith({ data: null, errors: [{ message: "Lookup failed" }] });

    // WHEN / THEN
    await expect(getRepositoryImportTaskFromApi(lookupParams)).rejects.toThrow("Lookup failed");
    expect(toast).not.toHaveBeenCalled();
  });

  it("reject a failed log fetch without showing the error toast", async () => {
    // GIVEN
    respondWith({ data: null, errors: [{ message: "Log fetch failed" }] });

    // WHEN / THEN
    await expect(getImportTaskLogsFromApi({ taskId: "task-1", logLimit: 10 })).rejects.toThrow(
      "Log fetch failed"
    );
    expect(toast).not.toHaveBeenCalled();
  });
});
