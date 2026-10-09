import { describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getNumberPoolForEditingFromApi } from "./get-number-pool-for-editing-from-api";

vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { query: vi.fn() },
}));

describe("getNumberPoolForEditingFromApi", () => {
  it("reads range bounds above 2^53 without rounding them", async () => {
    // WHEN
    await getNumberPoolForEditingFromApi({ branchName: "main", poolId: "pool-1" });

    // THEN
    expect(vi.mocked(graphqlClient.query).mock.calls[0]![0].context).toEqual({
      branch: "main",
      keepLargeIntegersExact: true,
    });
  });
});
