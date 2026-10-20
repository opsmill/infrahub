import { afterEach, describe, expect, test, vi } from "vitest";

import { TASK_FINAL_STATES } from "@/entities/tasks/domain/model/task";
import { checkTaskDetails } from "@/entities/tasks/domain/use-cases/check-task-details";
import { isTaskFinished } from "@/entities/tasks/domain/use-cases/is-task-finished";

vi.mock("@/entities/tasks/domain/use-cases/check-task-details");

afterEach(() => {
  vi.resetAllMocks();
});

describe("isTaskFinished", () => {
  test("is true when the task is in a final state", async () => {
    // GIVEN
    vi.mocked(checkTaskDetails).mockResolvedValue(1);

    // WHEN
    const result = await isTaskFinished({ taskId: "task-1" });

    // THEN
    expect(result).toBe(true);
    expect(checkTaskDetails).toHaveBeenCalledWith(
      { ids: ["task-1"], state: TASK_FINAL_STATES },
      { silenceErrors: true }
    );
  });

  test("is false while the task is not in a final state or not listed yet", async () => {
    // GIVEN
    vi.mocked(checkTaskDetails).mockResolvedValue(0);

    // WHEN
    const result = await isTaskFinished({ taskId: "task-1" });

    // THEN
    expect(result).toBe(false);
  });
});
