import { describe, expect, it, vi } from "vitest";

import { getArtifactContentDiffQueryOptions } from "./get-artifact-content-diff.query";

vi.mock("@/entities/diff/domain/get-artifact-content-diff", () => ({
  getArtifactContentDiff: vi.fn().mockResolvedValue({ threads: [] }),
}));

describe("getArtifactContentDiffQueryOptions", () => {
  it("builds a stable, object-form query key", () => {
    const opts = getArtifactContentDiffQueryOptions({ proposedChangeId: "pc-789" });

    expect(opts.queryKey).toEqual([
      "artifact-content-diff",
      "detail",
      { proposedChangeId: "pc-789" },
    ]);
  });
});
