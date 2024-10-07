import { describe, expect, it } from "vitest";
import { TreeProps } from "../../../../src/components/ui/tree";
import { generateRootCategoryNodeForDiffTree } from "../../../../src/screens/diff/diff-tree";
import { TREE_ROOT_ID } from "../../../../src/screens/ipam/constants";

describe("Generate root category nodes for DiffTree", () => {
  it("should return an empty array when no nodes are provided", () => {
    // GIVEN
    const diffTreeNodes: TreeProps["data"] = [];

    // WHEN
    const result = generateRootCategoryNodeForDiffTree(diffTreeNodes);

    // THEN
    expect(result).toEqual([]);
  });

  it("should return an empty array when all provided nodes are not root nodes", () => {
    // GIVEN
    const diffTreeNodes = [{ id: "1", parent: "not-root", metadata: { kind: "A" } }];

    // WHEN
    const result = generateRootCategoryNodeForDiffTree(diffTreeNodes);

    // THEN
    expect(result).toEqual([{ id: "1", parent: "not-root", metadata: { kind: "A" } }]);
  });

  it("should generate root category nodes for DiffTree with single node", () => {
    // GIVEN
    const diffTreeNodes = [{ id: "1", parent: TREE_ROOT_ID, metadata: { kind: "A" } }];

    // WHEN
    const result = generateRootCategoryNodeForDiffTree(diffTreeNodes);

    // THEN
    expect(result).toEqual([
      {
        id: "A",
        name: "A",
        parent: TREE_ROOT_ID,
        children: ["1"],
        isBranch: true,
        metadata: { kind: "A" },
      },
      { id: "1", parent: "A", metadata: { kind: "A" } },
    ]);
  });

  it("should generate root category nodes for DiffTree with multiple nodes of the same kind", () => {
    // GIVEN
    const diffTreeNodes = [
      { id: "1", parent: TREE_ROOT_ID, metadata: { kind: "A" } },
      { id: "2", parent: TREE_ROOT_ID, metadata: { kind: "A" } },
      { id: "3", parent: TREE_ROOT_ID, metadata: { kind: "A" } },
    ];

    // WHEN
    const result = generateRootCategoryNodeForDiffTree(diffTreeNodes);

    // THEN
    expect(result).toEqual([
      {
        id: "A",
        name: "A",
        parent: TREE_ROOT_ID,
        children: ["1", "2", "3"],
        isBranch: true,
        metadata: { kind: "A" },
      },
      { id: "1", parent: "A", metadata: { kind: "A" } },
      { id: "2", parent: "A", metadata: { kind: "A" } },
      { id: "3", parent: "A", metadata: { kind: "A" } },
    ]);
  });

  it("should generate root category nodes for DiffTree with multiple nodes of different kinds", () => {
    // GIVEN
    const diffTreeNodes = [
      { id: "1", parent: TREE_ROOT_ID, metadata: { kind: "A" } },
      { id: "2", parent: TREE_ROOT_ID, metadata: { kind: "B" } },
      { id: "3", parent: TREE_ROOT_ID, metadata: { kind: "C" } },
    ];

    // WHEN
    const result = generateRootCategoryNodeForDiffTree(diffTreeNodes);

    // THEN
    expect(result).toEqual([
      {
        id: "A",
        name: "A",
        parent: TREE_ROOT_ID,
        children: ["1"],
        isBranch: true,
        metadata: { kind: "A" },
      },
      { id: "1", parent: "A", metadata: { kind: "A" } },
      {
        id: "B",
        name: "B",
        parent: TREE_ROOT_ID,
        children: ["2"],
        isBranch: true,
        metadata: { kind: "B" },
      },
      { id: "2", parent: "B", metadata: { kind: "B" } },
      {
        id: "C",
        name: "C",
        parent: TREE_ROOT_ID,
        children: ["3"],
        isBranch: true,
        metadata: { kind: "C" },
      },
      { id: "3", parent: "C", metadata: { kind: "C" } },
    ]);
  });

  it("should not generate root category nodes for nodes that have no kind", () => {
    // GIVEN
    const diffTreeNodes = [
      { id: "1", parent: TREE_ROOT_ID },
      { id: "2", parent: TREE_ROOT_ID, metadata: { kind: "A" } },
    ];

    // WHEN
    const result = generateRootCategoryNodeForDiffTree(diffTreeNodes);

    // THEN
    expect(result).toEqual([
      { id: "1", parent: TREE_ROOT_ID },
      {
        id: "A",
        name: "A",
        parent: TREE_ROOT_ID,
        children: ["2"],
        isBranch: true,
        metadata: { kind: "A" },
      },
      { id: "2", parent: "A", metadata: { kind: "A" } },
    ]);
  });

  it("should not generate root category nodes for nodes that have null or undefined kind", () => {
    // GIVEN
    const diffTreeNodes = [
      { id: "1", parent: TREE_ROOT_ID, metadata: { kind: null } },
      { id: "2", parent: TREE_ROOT_ID, metadata: { kind: undefined } },
      { id: "3", parent: TREE_ROOT_ID, metadata: { kind: "A" } },
    ];

    // WHEN
    const result = generateRootCategoryNodeForDiffTree(diffTreeNodes);

    // THEN
    expect(result).toEqual([
      { id: "1", parent: TREE_ROOT_ID, metadata: { kind: null } },
      { id: "2", parent: TREE_ROOT_ID, metadata: { kind: undefined } },
      {
        id: "A",
        name: "A",
        parent: TREE_ROOT_ID,
        children: ["3"],
        isBranch: true,
        metadata: { kind: "A" },
      },
      { id: "3", parent: "A", metadata: { kind: "A" } },
    ]);
  });
});
