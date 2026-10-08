import { describe, expect, it } from "vitest";

import {
  getBranchFailedTaskCountQueryOptions,
  getBranchTasksQueryOptions,
} from "@/entities/tasks/ui/queries/get-branch-tasks.query";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const params = { branchName: "feature", offset: 0, limit: 10 };

const intervalOf = (
  refetchInterval: unknown,
  state: { status: string; error: Error | null } = { status: "success", error: null }
) => (typeof refetchInterval === "function" ? refetchInterval({ state }) : refetchInterval);

// The transport throws an Error whose cause is an error carrying the GraphQL errors.
const permissionDenied = () =>
  new Error("Denied", {
    cause: Object.assign(new Error("Denied"), {
      graphQLErrors: [
        {
          message: "Denied",
          extensions: { code: "PERMISSION_DENIED", http_status: 403, data: {} },
        },
      ],
    }),
  });

describe("getBranchTasksQueryOptions", () => {
  it("polls page 1 every 10 seconds, and no other page", () => {
    expect(intervalOf(getBranchTasksQueryOptions(params).refetchInterval)).toBe(10_000);
    expect(intervalOf(getBranchTasksQueryOptions({ ...params, offset: 10 }).refetchInterval)).toBe(
      false
    );
  });

  it("retries a failed page 1 every minute, and stops once it is denied", () => {
    const { refetchInterval } = getBranchTasksQueryOptions(params);
    expect(intervalOf(refetchInterval, { status: "error", error: new Error("Network") })).toBe(
      60_000
    );
    expect(intervalOf(refetchInterval, { status: "error", error: permissionDenied() })).toBe(false);
  });

  it("keys the page on the branch and its window", () => {
    expect(getBranchTasksQueryOptions({ ...params, offset: 20 }).queryKey).toEqual(
      tasksQueryKeys.branchList({ branchName: "feature", offset: 20, limit: 10 })
    );
  });

  describe("placeholder data", () => {
    const placeholderFor = (
      branchName: string,
      previousBranchName: string,
      previousTasks: unknown[] = [{ id: "task-1" }]
    ) => {
      const { placeholderData } = getBranchTasksQueryOptions({ ...params, branchName, offset: 10 });
      if (typeof placeholderData !== "function") throw new Error("expected a placeholder function");
      type Args = Parameters<typeof placeholderData>;
      const previousData = { tasks: previousTasks, count: 11 } as unknown as Args[0];
      const previousQuery = {
        queryKey: tasksQueryKeys.branchList({ ...params, branchName: previousBranchName }),
      } as unknown as Args[1];
      return { previousData, placeholder: placeholderData(previousData, previousQuery) };
    };

    it("keeps the previous page's rows while the same branch's next page loads", () => {
      const { previousData, placeholder } = placeholderFor("feature", "feature");

      expect(placeholder).toBe(previousData);
    });

    it("doesn't show another branch's rows while the new branch loads", () => {
      const { placeholder } = placeholderFor("feature", "other-branch");

      expect(placeholder).toBeUndefined();
    });

    it("doesn't keep a previous page without rows, such as a page past the end", () => {
      const { placeholder } = placeholderFor("feature", "feature", []);

      expect(placeholder).toBeUndefined();
    });
  });
});

describe("getBranchFailedTaskCountQueryOptions", () => {
  it("counts FAILED tasks only, the state the Tasks page link filters on", () => {
    expect(getBranchFailedTaskCountQueryOptions({ branchName: "feature" }).queryKey).toEqual(
      tasksQueryKeys.count({ branchName: "feature", state: ["FAILED"] })
    );
  });

  it("polls every 10 seconds, and stops once it is denied", () => {
    const { refetchInterval } = getBranchFailedTaskCountQueryOptions({ branchName: "feature" });
    expect(intervalOf(refetchInterval)).toBe(10_000);
    expect(intervalOf(refetchInterval, { status: "error", error: permissionDenied() })).toBe(false);
  });
});
