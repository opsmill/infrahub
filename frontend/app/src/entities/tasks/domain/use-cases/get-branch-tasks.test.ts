import { beforeEach, describe, expect, it, vi } from "vitest";

import { getTaskListFromApi } from "@/entities/tasks/api/get-task-list-from-api";

import { getBranchTasks } from "./get-branch-tasks";

vi.mock("@/entities/tasks/api/get-task-list-from-api");

type Response = Awaited<ReturnType<typeof getTaskListFromApi>>;

describe("getBranchTasks", () => {
  const mockGetTaskListFromApi = vi.mocked(getTaskListFromApi);

  beforeEach(() => {
    mockGetTaskListFromApi.mockReset();
  });

  it("returns the page of tasks and the total count", async () => {
    mockGetTaskListFromApi.mockResolvedValueOnce({
      data: {
        InfrahubTask: {
          count: 42,
          edges: [
            {
              node: {
                id: "task-1",
                branch: "feature",
                title: "Import repository",
                state: "FAILED",
                workflow: "git-repository-import-object",
                related_nodes: [{ id: "repo-1", kind: "CoreRepository" }, null],
                updated_at: "2026-09-29T10:00:00Z",
                progress: null,
              },
            },
            { node: null },
          ],
        },
      },
    } as unknown as Response);

    await expect(getBranchTasks({ branchName: "feature", offset: 10, limit: 10 })).resolves.toEqual(
      {
        count: 42,
        tasks: [
          {
            id: "task-1",
            title: "Import repository",
            branch: "feature",
            state: "FAILED",
            workflow: "git-repository-import-object",
            relatedNodes: [{ id: "repo-1", kind: "CoreRepository" }],
            updatedAt: "2026-09-29T10:00:00Z",
          },
        ],
      }
    );
  });

  it("passes the branch name, offset and limit, and leaves errors to the card", async () => {
    mockGetTaskListFromApi.mockResolvedValueOnce({
      data: { InfrahubTask: { count: 0, edges: [] } },
    } as unknown as Response);

    await getBranchTasks({ branchName: "feature", offset: 20, limit: 10 });

    expect(mockGetTaskListFromApi).toHaveBeenCalledWith(
      { branchName: "feature", offset: 20, limit: 10 },
      { silenceErrors: true }
    );
  });

  it("lets an api error through", async () => {
    mockGetTaskListFromApi.mockRejectedValueOnce(new Error("Task manager unavailable"));

    await expect(getBranchTasks({ branchName: "feature", offset: 0, limit: 10 })).rejects.toThrow(
      "Task manager unavailable"
    );
  });
});
