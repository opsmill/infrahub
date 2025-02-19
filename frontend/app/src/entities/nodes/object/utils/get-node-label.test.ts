import { NodeCore } from "@/entities/nodes/types";
import { describe, expect, it } from "vitest";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { getNodeLabel } from "./get-node-label";

describe("getNodeLabel", () => {
  const baseSchema = generateNodeSchema();
  const baseNode: NodeCore = {
    id: "test-id",
    hfid: null,
    display_label: null,
    __typename: "TestKind",
  };

  it("should join multiple hfids with comma when node has hfid array", () => {
    // GIVEN
    const node = { ...baseNode, hfid: ["hfid-1", "hfid-2"] };
    const schema = baseSchema;

    // WHEN
    const result = getNodeLabel({ node, schema });

    // THEN
    expect(result).toBe("hfid-1, hfid-2");
  });

  it("should use display_label when hfid is not present", () => {
    // GIVEN
    const node = { ...baseNode, display_label: "Display Label" };
    const schema = baseSchema;

    // WHEN
    const result = getNodeLabel({ node, schema });

    // THEN
    expect(result).toBe("Display Label");
  });

  it("should fallback to node.id when neither hfid nor display_label are present", () => {
    // WHEN
    const result = getNodeLabel({ node: baseNode, schema: baseSchema });

    // THEN
    expect(result).toBe("test-id");
  });

  it("should prefer hfid over display_label when both are available", () => {
    // GIVEN
    const node = {
      ...baseNode,
      hfid: ["hfid-1"],
      display_label: "Display Label",
    };
    const schema = baseSchema;

    // WHEN
    const result = getNodeLabel({ node, schema });

    // THEN
    expect(result).toBe("hfid-1");
  });

  it("should fallback to node.id when schema allows special labels but node values are null", () => {
    // GIVEN
    const schema = baseSchema;

    // WHEN
    const result = getNodeLabel({ node: baseNode, schema });

    // THEN
    expect(result).toBe("test-id");
  });

  it("should use node.id when schema disables special labels even if node has them", () => {
    // GIVEN
    const node = {
      ...baseNode,
      hfid: ["hfid-1"],
      display_label: "Display Label",
    };
    const schema = {
      ...baseSchema,
      human_friendly_id: null,
      display_labels: null,
    };

    // WHEN
    const result = getNodeLabel({ node, schema: schema });

    // THEN
    expect(result).toBe("test-id");
  });
});
