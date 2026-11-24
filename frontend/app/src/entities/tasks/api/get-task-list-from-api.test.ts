import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getTaskCountFromApi } from "./get-task-count-from-api";
import { getTaskListFromApi } from "./get-task-list-from-api";

vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

const mockQuery = vi.mocked(graphqlClient.query);

describe.each([
  ["getTaskListFromApi", getTaskListFromApi],
  ["getTaskCountFromApi", getTaskCountFromApi],
])("%s", (_, fetchTasks) => {
  beforeEach(() => {
    mockQuery.mockReset();
    mockQuery.mockResolvedValue({ data: { InfrahubTask: { count: 0, edges: [] } } });
  });

  it("leaves a failure to the error toast by default", async () => {
    // WHEN
    await fetchTasks({ branchName: "feature" });

    // THEN
    expect(mockQuery.mock.lastCall?.[0].context).toBeUndefined();
  });

  it("skips the error toast when the caller renders its own error state", async () => {
    // WHEN
    await fetchTasks({ branchName: "feature" }, { silenceErrors: true });

    // THEN
    expect(mockQuery.mock.lastCall?.[0].context?.processErrorMessage).toEqual(expect.any(Function));
  });
});
