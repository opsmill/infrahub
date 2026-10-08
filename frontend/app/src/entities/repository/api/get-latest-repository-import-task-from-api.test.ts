import { toast } from "react-toastify";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getLatestRepositoryImportTaskFromApi } from "./get-latest-repository-import-task-from-api";

vi.mock("react-toastify", () => ({ toast: vi.fn() }));

const params = { branch: "feature", repositoryId: "repo-1", workflows: [], states: [] };

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

describe("getLatestRepositoryImportTaskFromApi", () => {
  beforeEach(() => {
    vi.mocked(toast).mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks for the single newest task of the repository on the branch", async () => {
    // GIVEN
    respondWith({ data: { InfrahubTask: { edges: [] } } });
    const lookup = {
      branch: "feature",
      repositoryId: "repo-1",
      workflows: ["git-repository-import-object"],
      states: ["RUNNING", "FAILED"],
    };

    // WHEN
    await getLatestRepositoryImportTaskFromApi(lookup);

    // THEN
    const [, init] = vi.mocked(fetch).mock.calls[0] ?? [];
    const body = JSON.parse(String(init?.body));
    expect(body.variables).toEqual(lookup);
    expect(body.query).toMatch(/limit:\s*1\b/);
  });

  it("returns the id and state of the newest matching task", async () => {
    // GIVEN
    respondWith({
      data: { InfrahubTask: { edges: [{ node: { id: "task-1", state: "FAILED" } }] } },
    });

    // WHEN / THEN
    await expect(getLatestRepositoryImportTaskFromApi(params)).resolves.toEqual({
      id: "task-1",
      state: "FAILED",
    });
  });

  it("returns null when no task matches", async () => {
    // GIVEN
    respondWith({ data: { InfrahubTask: { edges: [] } } });

    // WHEN / THEN
    await expect(getLatestRepositoryImportTaskFromApi(params)).resolves.toBeNull();
  });

  it("rejects a failed lookup without showing the error toast", async () => {
    // GIVEN
    respondWith({ data: null, errors: [{ message: "Lookup failed" }] });

    // WHEN / THEN
    await expect(getLatestRepositoryImportTaskFromApi(params)).rejects.toThrow("Lookup failed");
    expect(toast).not.toHaveBeenCalled();
  });
});
