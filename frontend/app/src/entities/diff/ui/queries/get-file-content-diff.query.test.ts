import { describe, expect, it, vi } from "vitest";

import { getFileContentDiffQueryOptions } from "./get-file-content-diff.query";

vi.mock("@/entities/diff/domain/get-file-content-diff", () => ({
  getFileContentDiff: vi.fn().mockResolvedValue({ threads: [] }),
}));

describe("getFileContentDiffQueryOptions", () => {
  it("builds a stable, object-form query key", () => {
    const opts = getFileContentDiffQueryOptions({ proposedChangeId: "pc-abc" });

    expect(opts.queryKey).toEqual(["file-content-diff", "detail", { proposedChangeId: "pc-abc" }]);
  });
});
