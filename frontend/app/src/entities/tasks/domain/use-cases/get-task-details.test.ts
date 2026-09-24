import { beforeEach, describe, expect, it, vi } from "vitest";

import { getTaskDetailsFromApi } from "@/entities/tasks/api/get-task-details-from-api";

import { getTaskDetails } from "./get-task-details";

vi.mock("@/entities/tasks/api/get-task-details-from-api");

const EMPTY_RESPONSE = { data: { InfrahubTask: { count: 0, edges: [] } } } as Awaited<
  ReturnType<typeof getTaskDetailsFromApi>
>;

describe("getTaskDetails", () => {
  const mockGetTaskDetails = vi.mocked(getTaskDetailsFromApi);

  beforeEach(() => {
    mockGetTaskDetails.mockClear();
    mockGetTaskDetails.mockResolvedValue(EMPTY_RESPONSE);
  });

  it("asks for every workflow type when looking a run up by its id", async () => {
    // GIVEN
    const params = { ids: ["a-run-id"] };

    // WHEN
    await getTaskDetails(params);

    // THEN an internal run carries no namespace tag, so without this the page reports it missing
    expect(mockGetTaskDetails).toHaveBeenCalledWith({
      ids: ["a-run-id"],
      workflowType: ["CORE", "USER", "INTERNAL"],
    });
  });

  it("leaves a listing query's scope untouched", async () => {
    // GIVEN
    const params = { branch: "main", workflow: ["branch-merge"] };

    // WHEN
    await getTaskDetails(params);

    // THEN
    expect(mockGetTaskDetails).toHaveBeenCalledWith(params);
  });

  it("does not override an explicit type selection", async () => {
    // GIVEN
    const params = { ids: ["a-run-id"], workflowType: ["INTERNAL" as const] };

    // WHEN
    await getTaskDetails(params);

    // THEN
    expect(mockGetTaskDetails).toHaveBeenCalledWith(params);
  });
});
