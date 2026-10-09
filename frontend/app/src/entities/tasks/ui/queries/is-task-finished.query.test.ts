import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { isTaskFinished } from "@/entities/tasks/domain/use-cases/is-task-finished";
import { isTaskFinishedQueryOptions } from "@/entities/tasks/ui/queries/is-task-finished.query";

vi.mock("@/entities/tasks/domain/use-cases/is-task-finished");

afterEach(() => {
  vi.resetAllMocks();
});

const checkTask = async (isFinished: boolean) => {
  vi.mocked(isTaskFinished).mockResolvedValue(isFinished);
  const queryClient = new QueryClient();
  const options = isTaskFinishedQueryOptions({ taskId: "task-1" });
  await queryClient.fetchQuery(options);

  return new QueryObserver(queryClient, options).getCurrentResult();
};

const checkRunningTaskTimes = (count: number) => {
  const queryClient = new QueryClient();
  const options = isTaskFinishedQueryOptions({ taskId: "task-1" });
  for (let check = 0; check < count; check += 1) {
    queryClient.setQueryData(options.queryKey, false);
  }

  return new QueryObserver(queryClient, options).getCurrentResult();
};

describe("isTaskFinishedQueryOptions", () => {
  test("never checks a finished task again on focus, reconnect or remount", async () => {
    // WHEN
    const result = await checkTask(true);

    // THEN
    expect(result.isStale).toBe(false);
  });

  test("checks a running task again on focus, reconnect or remount", async () => {
    // WHEN
    const result = await checkTask(false);

    // THEN
    expect(result.isStale).toBe(true);
  });

  test("stops checking a task that never finishes after 360 checks", () => {
    expect(checkRunningTaskTimes(359).isStale).toBe(true);
    expect(checkRunningTaskTimes(360).isStale).toBe(false);
  });
});
