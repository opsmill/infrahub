import { describe, expect, test } from "vitest";

import {
  type GeneratorDefinitionTargetData,
  selectNodeGeneratorDefinitions,
} from "@/entities/generators/domain/rules/select-node-generator-definitions";

const definition = (
  name: string,
  groupName: string,
  memberCount: number
): GeneratorDefinitionTargetData => ({
  id: `${name}-id`,
  display_label: name,
  targets: {
    node: { id: `${groupName}-id`, display_label: groupName, members: { count: memberCount } },
  },
});

describe("selectNodeGeneratorDefinitions", () => {
  test("returns nothing when no generator definition exists", () => {
    // GIVEN
    const kindCountByGroupId = new Map<string, number>();

    // WHEN
    const result = selectNodeGeneratorDefinitions({ definitions: [], kindCountByGroupId });

    // THEN
    expect(result).toEqual([]);
  });

  test("skips a definition whose target group holds no node of the kind", () => {
    // GIVEN
    const definitions = [definition("generate-pod", "pods", 0)];
    const kindCountByGroupId = new Map([["pods-id", 0]]);

    // WHEN
    const result = selectNodeGeneratorDefinitions({ definitions, kindCountByGroupId });

    // THEN
    expect(result).toEqual([]);
  });

  test("skips a definition whose target group has no kind count", () => {
    // GIVEN
    const definitions = [definition("generate-pod", "pods", 0)];
    const kindCountByGroupId = new Map<string, number>();

    // WHEN
    const result = selectNodeGeneratorDefinitions({ definitions, kindCountByGroupId });

    // THEN
    expect(result).toEqual([]);
  });

  test("marks the node as a member when the target group contains it", () => {
    // GIVEN
    const definitions = [definition("generate-fabric", "fabrics", 1)];
    const kindCountByGroupId = new Map([["fabrics-id", 4]]);

    // WHEN
    const result = selectNodeGeneratorDefinitions({ definitions, kindCountByGroupId });

    // THEN
    expect(result).toEqual([
      {
        id: "generate-fabric-id",
        label: "generate-fabric",
        groupId: "fabrics-id",
        groupLabel: "fabrics",
        isMember: true,
      },
    ]);
  });

  test("keeps a definition for a node of the targeted kind that is not a member", () => {
    // GIVEN
    const definitions = [definition("generate-fabric", "fabrics", 0)];
    const kindCountByGroupId = new Map([["fabrics-id", 4]]);

    // WHEN
    const result = selectNodeGeneratorDefinitions({ definitions, kindCountByGroupId });

    // THEN
    expect(result).toEqual([
      {
        id: "generate-fabric-id",
        label: "generate-fabric",
        groupId: "fabrics-id",
        groupLabel: "fabrics",
        isMember: false,
      },
    ]);
  });

  test("returns one entry per definition when two definitions share a target group", () => {
    // GIVEN
    const definitions = [
      definition("generate-fabric", "fabrics", 1),
      definition("cabling-plan", "fabrics", 1),
    ];
    const kindCountByGroupId = new Map([["fabrics-id", 4]]);

    // WHEN
    const result = selectNodeGeneratorDefinitions({ definitions, kindCountByGroupId });

    // THEN
    expect(result.map(({ label }) => label)).toEqual(["generate-fabric", "cabling-plan"]);
  });

  test("skips a definition without a target group", () => {
    // GIVEN
    const definitions: GeneratorDefinitionTargetData[] = [
      { id: "orphan-id", display_label: "orphan", targets: { node: null } },
    ];
    const kindCountByGroupId = new Map([["fabrics-id", 4]]);

    // WHEN
    const result = selectNodeGeneratorDefinitions({ definitions, kindCountByGroupId });

    // THEN
    expect(result).toEqual([]);
  });
});
