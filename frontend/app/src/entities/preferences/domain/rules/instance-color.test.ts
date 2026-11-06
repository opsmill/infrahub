import { describe, expect, test } from "vitest";

import {
  instanceBadgeVariant,
  instanceBarClassName,
} from "@/entities/preferences/domain/rules/instance-color";

describe("instance color presets", () => {
  test.each([
    { name: "no color", color: null },
    { name: "a color this bundle does not know", color: "TEAL" },
  ])("renders $name as unset", ({ color }) => {
    expect(instanceBadgeVariant(color)).toBe("gray");
    expect(instanceBarClassName(color)).toBeNull();
  });
});
