import { describe, expect, it } from "vitest";

import {
  getBranchFailedTaskCountQueryOptions,
  getBranchTasksQueryOptions,
} from "@/entities/tasks/ui/queries/get-branch-tasks.query";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const params = { branchName: "feature", offset: 0, limit: 10 };

describe("getBranchTasksQueryOptions", () => {
  it("polls page 1 every 10 seconds, and no other page", () => {
    expect(getBranchTasksQueryOptions(params).refetchInterval).toBe(10_000);
    expect(getBranchTasksQueryOptions({ ...params, offset: 10 }).refetchInterval).toBe(false);
  });

  it("keys the page on the branch and its window", () => {
    expect(getBranchTasksQueryOptions({ ...params, offset: 20 }).queryKey).toEqual(
      tasksQueryKeys.branchList({ branchName: "feature", offset: 20, limit: 10 })
    );
  });

  describe("placeholder data", () => {
    const placeholderFor = (branchName: string, previousBranchName: string) => {
      const { placeholderData } = getBranchTasksQueryOptions({ ...params, branchName, offset: 10 });
      if (typeof placeholderData !== "function") throw new Error("expected a placeholder function");
      type Args = Parameters<typeof placeholderData>;
      const previousData = { previous: true } as unknown as Args[0];
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
  });
});

describe("getBranchFailedTaskCountQueryOptions", () => {
  it("counts FAILED tasks only, the state the Tasks page link filters on", () => {
    expect(getBranchFailedTaskCountQueryOptions({ branchName: "feature" }).queryKey).toEqual(
      tasksQueryKeys.count({ branchName: "feature", state: ["FAILED"] })
    );
  });

  it("polls every 10 seconds", () => {
    expect(getBranchFailedTaskCountQueryOptions({ branchName: "feature" }).refetchInterval).toBe(
      10_000
    );
  });
});
