import { beforeEach, describe, expect, it, vi } from "vitest";

import { retryTaskFromApi } from "@/entities/tasks/api/retry-task-from-api";

import { retryTask } from "./retry-task";

vi.mock("@/entities/tasks/api/retry-task-from-api");

describe("retryTask", () => {
  const mockRetryTaskFromApi = vi.mocked(retryTaskFromApi);

  beforeEach(() => {
    mockRetryTaskFromApi.mockClear();
  });

  it("returns the id of the new delivery", async () => {
    mockRetryTaskFromApi.mockResolvedValueOnce({
      data: { InfrahubTaskRetry: { ok: true, task: { id: "new-run-1" } } },
    } as Awaited<ReturnType<typeof retryTaskFromApi>>);

    await expect(retryTask({ id: "run-1" })).resolves.toBe("new-run-1");
  });

  it("returns undefined when the response carries no task id", async () => {
    mockRetryTaskFromApi.mockResolvedValueOnce({
      data: { InfrahubTaskRetry: { ok: true, task: null } },
    } as Awaited<ReturnType<typeof retryTaskFromApi>>);

    await expect(retryTask({ id: "run-1" })).resolves.toBeUndefined();
  });

  it("throws when the response carries errors", async () => {
    mockRetryTaskFromApi.mockResolvedValueOnce({
      data: null,
      errors: [{ message: "This delivery is no longer available." }],
    } as unknown as Awaited<ReturnType<typeof retryTaskFromApi>>);

    await expect(retryTask({ id: "run-1" })).rejects.toThrow(
      "This delivery is no longer available."
    );
  });

  it("propagates a rejected api call to the caller", async () => {
    mockRetryTaskFromApi.mockRejectedValueOnce(new Error("This delivery is no longer available."));

    await expect(retryTask({ id: "run-1" })).rejects.toThrow(
      "This delivery is no longer available."
    );
  });
});
