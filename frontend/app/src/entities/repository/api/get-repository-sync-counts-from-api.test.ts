import { print } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_SYNC_STATUS_ERROR_VALUE,
} from "@/entities/repository/domain/model/repository";

import { getRepositorySyncCountsFromApi } from "./get-repository-sync-counts-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// the query. Keep that real and stub only the transport.
vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

const queryMock = vi.mocked(graphqlClient.query);

const sentRequest = () => {
  const [request] = queryMock.mock.calls.at(0) ?? [];
  if (!request) throw new Error("no request was sent");
  return request;
};

const sentQuery = () => print(sentRequest().query as never);

describe("getRepositorySyncCountsFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryMock.mockResolvedValue({
      data: { total: { count: 0 }, failing: { count: 0 } },
    } as never);
  });

  it("asks for both counts in a single request", async () => {
    // WHEN
    await getRepositorySyncCountsFromApi({ branchName: "branch1", atDate: null });

    // THEN
    expect(queryMock).toHaveBeenCalledTimes(1);
    expect(sentQuery()).toContain("total:");
    expect(sentQuery()).toContain("failing:");
  });

  it("counts every repository kind through the generic kind", async () => {
    // WHEN
    await getRepositorySyncCountsFromApi({ branchName: "branch1", atDate: null });

    // THEN both aliases resolve to the generic kind, so no concrete kind is missed
    const query = sentQuery();
    expect(query).toContain(`total: ${GENERIC_REPOSITORY_KIND}`);
    expect(query).toContain(`failing: ${GENERIC_REPOSITORY_KIND}`);
  });

  it("narrows only the failing count to the import error", async () => {
    // WHEN
    await getRepositorySyncCountsFromApi({ branchName: "branch1", atDate: null });

    // THEN
    const [totalPart, failingPart] = sentQuery().split("failing:");
    expect(totalPart).not.toContain(REPOSITORY_SYNC_STATUS_ERROR_VALUE);
    expect(failingPart).toContain(REPOSITORY_SYNC_STATUS_ERROR_VALUE);
  });

  it("carries the branch and the requested moment to the transport", async () => {
    // WHEN
    await getRepositorySyncCountsFromApi({ branchName: "branch1", atDate: null });

    // THEN
    expect(sentRequest().context).toMatchObject({
      branch: "branch1",
      date: null,
    });
  });
});
