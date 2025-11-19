import { describe, expect, it, vi } from "vitest";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";
import { getSchema } from "@/entities/schema/domain/get-schema";

import { generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/entities/schema/domain/get-schema", () => ({
  getSchema: vi.fn(() => ({
    schema: generateNodeSchema(),
    isGeneric: false,
    isNode: true,
    isProfile: false,
    isTemplate: false,
  })),
}));

describe("getNodeLabel", () => {
  const baseNode: NodeCore = {
    id: "test-id",
    hfid: null,
    display_label: null,
    __typename: "TestKind",
  };

  it("should join multiple hfids with comma when node has hfid array", () => {
    // GIVEN
    const node: NodeCore = { ...baseNode, hfid: ["hfid-1", "hfid-2"] };

    // WHEN
    const result = getNodeLabel(node);

    // THEN
    expect(result).toBe("hfid-1, hfid-2");
  });

  it("should use display_label when hfid is not present", () => {
    // GIVEN
    const node: NodeCore = { ...baseNode, display_label: "Display Label" };

    // WHEN
    const result = getNodeLabel(node);

    // THEN
    expect(result).toBe("Display Label");
  });

  it("should fallback to node.id when neither hfid nor display_label are present", () => {
    // WHEN
    const result = getNodeLabel(baseNode);

    // THEN
    expect(result).toBe("test-id");
  });

  it("should prefer hfid over display_label when both are available", () => {
    // GIVEN
    const node: NodeCore = {
      ...baseNode,
      hfid: ["hfid-1"],
      display_label: "Display Label",
    };

    // WHEN
    const result = getNodeLabel(node);

    // THEN
    expect(result).toBe("hfid-1");
  });

  it("should fallback to node.id when special labels are null", () => {
    // WHEN
    const result = getNodeLabel(baseNode);

    // THEN
    expect(result).toBe("test-id");
  });

  it("should use node.id when schema is not found even if node has special labels", () => {
    // GIVEN
    vi.mocked(getSchema).mockReturnValueOnce({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
      isTemplate: false,
    });
    const node: NodeCore = {
      ...baseNode,
      hfid: ["hfid-1"],
      display_label: "Display Label",
      __typename: "UnknownType",
    };

    // WHEN
    const result = getNodeLabel(node);

    // THEN
    expect(result).toBe("test-id");
  });
});
