import { describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { createNumberPoolRangeFromApi } from "./create-number-pool-range-from-api";

vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { mutate: vi.fn() },
}));

describe("createNumberPoolRangeFromApi", () => {
  it("sends bounds above 2^53 as exact strings", async () => {
    // GIVEN
    const range = { start: 1n, end: 9223372036854775807n, weight: 3 };

    // WHEN
    await createNumberPoolRangeFromApi({ branchName: "main", poolId: "pool-1", range });

    // THEN
    expect(vi.mocked(graphqlClient.mutate).mock.calls[0]![0].variables).toEqual({
      poolId: "pool-1",
      start: "1",
      end: "9223372036854775807",
      weight: 3,
    });
  });
});
