import { describe, expect, it, vi } from "vitest";

import { getDiffCommentsQueryOptions } from "./get-diff-comments.query";

vi.mock("@/entities/diff/domain/get-diff-comments", () => ({
  getDiffComments: vi.fn().mockResolvedValue({ thread: null }),
}));

describe("getDiffCommentsQueryOptions", () => {
  it("builds a stable, object-form query key", () => {
    const opts = getDiffCommentsQueryOptions({
      proposedChangeId: "pc-123",
      objectPath: "some/path",
    });

    expect(opts.queryKey).toEqual([
      "diff-comments",
      "detail",
      { proposedChangeId: "pc-123", objectPath: "some/path" },
    ]);
  });
});
