import { describe, expect, it } from "vitest";

import { formatElapsed } from "@/entities/repository/ui/repository-activity-card/elapsed-time";

describe("formatElapsed", () => {
  it.each([
    [45_000, "45s"],
    [64_000, "1m 04s"],
    [2 * 3_600_000 + 5 * 60_000, "2h 05m"],
    [-3000, "0s"],
  ])("formats %i ms as %s", (ms, expected) => {
    expect(formatElapsed(ms)).toBe(expected);
  });
});
