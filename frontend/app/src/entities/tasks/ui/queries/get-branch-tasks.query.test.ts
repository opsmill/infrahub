import { describe, expect, it } from "vitest";

import {
  getBranchFailedTaskCountQueryOptions,
  getBranchTasksQueryOptions,
} from "@/entities/tasks/ui/queries/get-branch-tasks.query";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

describe("getBranchTasksQueryOptions", () => {
  it("polls page 1 every 10 seconds", () => {
    expect(getBranchTasksQueryOptions({ branchName: "feature", page: 1 }).refetchInterval).toBe(
      10_000
    );
  });

  it("doesn't poll other pages", () => {
    expect(getBranchTasksQueryOptions({ branchName: "feature", page: 2 }).refetchInterval).toBe(
      false
    );
  });

  it("requests the page's offset", () => {
    expect(getBranchTasksQueryOptions({ branchName: "feature", page: 3 }).queryKey).toEqual(
      tasksQueryKeys.branchList({ branchName: "feature", offset: 20, limit: 10 })
    );
  });

  it("requests page 1 for a page below 1", () => {
    const options = getBranchTasksQueryOptions({ branchName: "feature", page: 0 });

    expect(options.queryKey).toEqual(
      tasksQueryKeys.branchList({ branchName: "feature", offset: 0, limit: 10 })
    );
    expect(options.refetchInterval).toBe(10_000);
    expect(getBranchTasksQueryOptions({ branchName: "feature", page: -4 }).queryKey).toEqual(
      tasksQueryKeys.branchList({ branchName: "feature", offset: 0, limit: 10 })
    );
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
