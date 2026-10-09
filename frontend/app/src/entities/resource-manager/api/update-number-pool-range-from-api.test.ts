import { describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { updateNumberPoolRangeFromApi } from "./update-number-pool-range-from-api";

vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { mutate: vi.fn() },
}));

describe("updateNumberPoolRangeFromApi", () => {
  it("sends bounds above 2^53 as exact strings", async () => {
    // GIVEN
    const range = {
      id: "range-1",
      start: 9007199254740993n,
      end: 9223372036854775807n,
      weight: null,
    };

    // WHEN
    await updateNumberPoolRangeFromApi({ branchName: "main", range });

    // THEN
    expect(vi.mocked(graphqlClient.mutate).mock.calls[0]![0].variables).toEqual({
      id: "range-1",
      start: "9007199254740993",
      end: "9223372036854775807",
      weight: null,
    });
  });
});
