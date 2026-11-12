import { describe, expect, it } from "vitest";

import { truncateLabel } from "./truncate-label";

describe("truncateLabel", () => {
  it("keeps a label that fits", () => {
    expect(truncateLabel("leaf1", 5)).toBe("leaf1");
  });

  it("cuts a longer label and ends it with an ellipsis", () => {
    expect(truncateLabel("leaf1-long-name", 8)).toBe("leaf1-l…");
  });

  it("keeps only the ellipsis when no room is left", () => {
    expect(truncateLabel("leaf1", 1)).toBe("…");
  });
});
