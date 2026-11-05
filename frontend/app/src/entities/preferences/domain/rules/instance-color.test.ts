import { describe, expect, test } from "vitest";

import {
  instanceBadgeVariant,
  instanceBarClassName,
  instanceColorLabel,
} from "@/entities/preferences/domain/rules/instance-color";

import { generateConfig } from "../../../../../tests/fake/config";

describe("instance color presets", () => {
  test.each([
    { color: "RED", badgeVariant: "red", barClassName: "bg-danger", label: "Red" },
    { color: "AMBER", badgeVariant: "warning", barClassName: "bg-warning-strong", label: "Amber" },
    { color: "GREEN", badgeVariant: "green", barClassName: "bg-success", label: "Green" },
    { color: "BLUE", badgeVariant: "blue", barClassName: "bg-info", label: "Blue" },
    { color: "INDIGO", badgeVariant: "indigo", barClassName: "bg-active", label: "Indigo" },
    {
      color: "PURPLE",
      badgeVariant: "purple",
      barClassName: "bg-purple-600 dark:bg-purple-400",
      label: "Purple",
    },
    { color: "GRAY", badgeVariant: "gray", barClassName: "bg-foreground-muted", label: "Gray" },
  ] as const)("maps $color to its badge variant, bar class and label", (preset) => {
    // GIVEN a preset color
    const { color } = preset;

    // WHEN the badge variant, the bar class and the label are resolved
    const resolved = {
      badgeVariant: instanceBadgeVariant(color),
      barClassName: instanceBarClassName(color),
      label: instanceColorLabel(color),
    };

    // THEN each matches the preset table
    expect(resolved).toEqual({
      badgeVariant: preset.badgeVariant,
      barClassName: preset.barClassName,
      label: preset.label,
    });
  });

  test("falls back to the gray badge variant when the instance has no color", () => {
    // GIVEN a config whose instance carries no color
    const config = generateConfig();

    // WHEN the badge variant is resolved
    const variant = instanceBadgeVariant(config.instance.color);

    // THEN it is gray
    expect(variant).toBe("gray");
  });

  test("falls back to the gray badge variant for a color this bundle does not know", () => {
    // GIVEN a color key served by a newer server
    const color = "TEAL";

    // WHEN the badge variant is resolved
    const variant = instanceBadgeVariant(color);

    // THEN it is gray
    expect(variant).toBe("gray");
  });

  test("resolves no bar class for a color this bundle does not know", () => {
    // GIVEN a color key served by a newer server
    const color = "TEAL";

    // WHEN the bar class is resolved
    const barClassName = instanceBarClassName(color);

    // THEN there is none
    expect(barClassName).toBeNull();
  });
});
