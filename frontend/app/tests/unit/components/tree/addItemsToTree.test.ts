import { describe, it, expect } from "vitest";
import { addItemsToTree } from "@/screens/ipam/ipam-tree/utils";
import { EMPTY_TREE } from "@/screens/ipam/ipam-tree/utils";
import { TreeProps } from "@/components/ui/tree";
import { TREE_ROOT_ID } from "@/screens/ipam/constants";

describe("Add items to tree", () => {
  it("should return the original tree when no items are provided", () => {
    // GIVEN
    const currentTreeItems: TreeProps["data"] = EMPTY_TREE;
    const newTreeItems: TreeProps["data"] = [];

    // WHEN
    const result = addItemsToTree(currentTreeItems, newTreeItems);

    // THEN
    expect(result).toEqual(EMPTY_TREE);
  });

  it("should add a single item to the tree", () => {
    // GIVEN
    const currentTreeItems: TreeProps["data"] = EMPTY_TREE;
    const newTreeItems: TreeProps["data"] = [
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: [] },
    ];

    // WHEN
    const result = addItemsToTree(currentTreeItems, newTreeItems);

    // THEN
    expect(result).toEqual([
      { id: TREE_ROOT_ID, name: "", parent: null, children: ["1"] },
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: [] },
    ]);
  });

  it("should add multiple items without children to the tree", () => {
    // GIVEN
    const currentTreeItems: TreeProps["data"] = EMPTY_TREE;
    const newTreeItems: TreeProps["data"] = [
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: [] },
      { id: "2", parent: TREE_ROOT_ID, name: "Item 2", children: [] },
    ];

    // WHEN
    const result = addItemsToTree(currentTreeItems, newTreeItems);

    // THEN
    expect(result).toEqual([
      { id: TREE_ROOT_ID, name: "", parent: null, children: ["1", "2"] },
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: [] },
      { id: "2", parent: TREE_ROOT_ID, name: "Item 2", children: [] },
    ]);
  });

  it("should add multiple items without/with children to the tree", () => {
    // GIVEN
    const currentTreeItems: TreeProps["data"] = EMPTY_TREE;
    const newTreeItems: TreeProps["data"] = [
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: [] },
      { id: "2", parent: TREE_ROOT_ID, name: "Item 2", children: [] },
      { id: "3", parent: "1", name: "Item 3", children: [] },
    ];

    // WHEN
    const result = addItemsToTree(currentTreeItems, newTreeItems);

    // THEN
    expect(result).toEqual([
      { id: TREE_ROOT_ID, name: "", parent: null, children: ["1", "2"] },
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: ["3"] },
      { id: "2", parent: TREE_ROOT_ID, name: "Item 2", children: [] },
      { id: "3", parent: "1", name: "Item 3", children: [] },
    ]);
  });

  it("should handle items with the same parent correctly", () => {
    // GIVEN
    const currentTreeItems: TreeProps["data"] = EMPTY_TREE;
    const newTreeItems = [
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: [] },
      { id: "2", parent: "1", name: "Item 2", children: [] },
      { id: "3", parent: "1", name: "Item 3", children: [] },
    ];

    // WHEN
    const result = addItemsToTree(currentTreeItems, newTreeItems);

    // THEN
    expect(result).toEqual([
      { id: TREE_ROOT_ID, name: "", parent: null, children: ["1"] },
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: ["2", "3"] },
      { id: "2", parent: "1", name: "Item 2", children: [] },
      { id: "3", parent: "1", name: "Item 3", children: [] },
    ]);
  });

  it("should handle items with different parents correctly", () => {
    // GIVEN
    const currentTreeItems: TreeProps["data"] = EMPTY_TREE;
    const newTreeItems = [
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: [] },
      { id: "2", parent: "1", name: "Item 2", children: [] },
      { id: "3", parent: "2", name: "Item 3", children: [] },
    ];

    // WHEN
    const result = addItemsToTree(currentTreeItems, newTreeItems);

    // THEN
    expect(result).toEqual([
      { id: TREE_ROOT_ID, name: "", parent: null, children: ["1"] },
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: ["2"] },
      { id: "2", parent: "1", name: "Item 2", children: ["3"] },
      { id: "3", parent: "2", name: "Item 3", children: [] },
    ]);
  });

  it("should handle nested children correctly", () => {
    // GIVEN
    const currentTreeItems: TreeProps["data"] = EMPTY_TREE;
    const newTreeItems = [
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: [] },
      { id: "2", parent: "3", name: "Item 2", children: [] },
      { id: "3", parent: "2", name: "Item 3", children: [] },
      { id: "4", parent: "1", name: "Item 4", children: [] },
    ];

    // WHEN
    const result = addItemsToTree(currentTreeItems, newTreeItems);

    // THEN
    expect(result).toEqual([
      { id: TREE_ROOT_ID, name: "", parent: null, children: ["1"] },
      { id: "1", parent: TREE_ROOT_ID, name: "Item 1", children: ["4"] },
      { id: "2", parent: "3", name: "Item 2", children: ["3"] },
      { id: "3", parent: "2", name: "Item 3", children: ["2"] },
      { id: "4", parent: "1", name: "Item 4", children: [] },
    ]);
  });

  it("should not duplicated key in children", () => {
    // GIVEN
    const currentTreeItems: TreeProps["data"] = [
      { id: "0", parent: TREE_ROOT_ID, name: "Item 0", children: ["1"] },
      { id: "1", parent: "0", name: "Item 1", children: [] },
    ];
    const newTreeItems = [
      { id: "1", parent: "0", name: "Item 1.1", children: [] },
      { id: "2", parent: "0", name: "Item 2", children: [] },
    ];

    // WHEN
    const result = addItemsToTree(currentTreeItems, newTreeItems);

    // THEN
    expect(result).toEqual([
      { id: "0", parent: TREE_ROOT_ID, name: "Item 0", children: ["1", "2"] },
      { id: "1", parent: "0", name: "Item 1.1", children: [] },
      { id: "2", parent: "0", name: "Item 2", children: [] },
    ]);
  });
});
