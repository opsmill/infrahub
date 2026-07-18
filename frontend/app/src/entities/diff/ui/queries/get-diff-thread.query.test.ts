import { describe, expect, it, vi } from "vitest";

import { getDiffThreadQueryOptions } from "./get-diff-thread.query";

vi.mock("@/entities/diff/domain/get-diff-thread", () => ({
  getDiffThread: vi.fn().mockResolvedValue({ thread: null, permissions: null }),
}));

describe("getDiffThreadQueryOptions", () => {
  it("builds a stable, object-form query key", () => {
    const opts = getDiffThreadQueryOptions({
      proposedChangeId: "pc-456",
      objectPath: "node/path",
    });

    expect(opts.queryKey).toEqual([
      "diff-thread",
      "detail",
      { proposedChangeId: "pc-456", objectPath: "node/path" },
    ]);
  });
});
