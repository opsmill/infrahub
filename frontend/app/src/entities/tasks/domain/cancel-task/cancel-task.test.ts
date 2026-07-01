import { beforeEach, describe, expect, it, vi } from "vitest";

import { cancelTaskFromApi } from "@/entities/tasks/api/cancel-task-from-api";

import { cancelTask } from "./cancel-task";

vi.mock("@/entities/tasks/api/cancel-task-from-api");

describe("cancelTask", () => {
  const mockCancelTaskFromApi = vi.mocked(cancelTaskFromApi);

  beforeEach(() => {
    mockCancelTaskFromApi.mockClear();
  });

  it("returns the id of the cancelled delivery", async () => {
    mockCancelTaskFromApi.mockResolvedValueOnce({
      data: { InfrahubTaskCancel: { ok: true, task: { id: "run-1" } } },
    } as Awaited<ReturnType<typeof cancelTaskFromApi>>);

    await expect(cancelTask({ id: "run-1" })).resolves.toBe("run-1");
  });

  it("returns undefined when the response carries no task id", async () => {
    mockCancelTaskFromApi.mockResolvedValueOnce({
      data: { InfrahubTaskCancel: { ok: true, task: null } },
    } as Awaited<ReturnType<typeof cancelTaskFromApi>>);

    await expect(cancelTask({ id: "run-1" })).resolves.toBeUndefined();
  });

  it("throws when the response carries errors", async () => {
    mockCancelTaskFromApi.mockResolvedValueOnce({
      data: null,
      errors: [{ message: "This delivery settled before it could be cancelled." }],
    } as unknown as Awaited<ReturnType<typeof cancelTaskFromApi>>);

    await expect(cancelTask({ id: "run-1" })).rejects.toThrow(
      "This delivery settled before it could be cancelled."
    );
  });

  it("propagates a rejected api call to the caller", async () => {
    mockCancelTaskFromApi.mockRejectedValueOnce(
      new Error("This delivery settled before it could be cancelled.")
    );

    await expect(cancelTask({ id: "run-1" })).rejects.toThrow(
      "This delivery settled before it could be cancelled."
    );
  });
});
