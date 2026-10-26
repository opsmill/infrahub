import { describe, expect, test } from "vitest";

import { getCompareWebUrl } from "@/entities/repository/domain/rules/get-compare-web-url";

const LOCATION = "https://github.com/opsmill/infrahub-demo.git";
const BASE = "0123456789abcdef0123456789abcdef01234567";
const HEAD = "fedcba9876543210fedcba9876543210fedcba98";

describe("getCompareWebUrl", () => {
  test("builds the compare page URL from the base to the head", () => {
    expect(getCompareWebUrl(LOCATION, BASE, HEAD)).toBe(
      `https://github.com/opsmill/infrahub-demo/compare/${BASE}...${HEAD}`
    );
  });

  test("returns null for a remote that is not on GitHub", () => {
    expect(getCompareWebUrl("https://gitlab.com/opsmill/infrahub-demo.git", BASE, HEAD)).toBeNull();
  });

  test.each([
    ["base", "main", HEAD],
    ["head", BASE, "../../settings"],
  ])("returns null when the %s is not a commit hash", (_label, base, head) => {
    expect(getCompareWebUrl(LOCATION, base, head)).toBeNull();
  });
});
