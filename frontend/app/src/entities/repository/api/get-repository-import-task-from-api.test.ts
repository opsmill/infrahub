import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import {
  getImportTaskLogsFromApi,
  getRepositoryImportTaskFromApi,
} from "./get-repository-import-task-from-api";

vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

const mockQuery = vi.mocked(graphqlClient.query);

describe("repository import task fetchers", () => {
  beforeEach(() => {
    mockQuery.mockReset();
    mockQuery.mockResolvedValue({ data: { InfrahubTask: { edges: [] } } });
  });

  it("leave a failed lookup to the band instead of showing the error toast", async () => {
    // WHEN
    await getRepositoryImportTaskFromApi({
      branch: "feature",
      repositoryId: "repo-1",
      workflows: [],
      states: [],
    });
    await getImportTaskLogsFromApi({ taskId: "task-1", logLimit: 10 });

    // THEN
    expect(mockQuery).toHaveBeenCalledTimes(2);
    for (const [request] of mockQuery.mock.calls) {
      expect(request.context?.processErrorMessage).toEqual(expect.any(Function));
    }
  });
});
