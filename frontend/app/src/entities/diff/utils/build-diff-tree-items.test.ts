import { beforeAll, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import type { DiffNode } from "@/entities/diff/node-diff/types";
import { buildDiffTreeItems, type DiffTreeItem } from "@/entities/diff/utils/build-diff-tree-items";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { generateNodeSchema } from "../../../../tests/fake/schema";

describe("buildDiffTreeItems", () => {
  beforeAll(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({ kind: "TestNode", label: "Test Node" }),
      generateNodeSchema({ kind: "TestNode2", label: "Test Node 2" }),
    ]);
  });

  it("returns an empty array if no nodes are provided", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [];

    // WHEN
    const result = buildDiffTreeItems(nodes);

    // THEN
    expect(result).toEqual([]);
  });

  it("returns tree items for one node", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "123",
        kind: "TestNode",
        label: "Test Node",
        status: "ADDED",
        attributes: [],
        relationships: [],
        contains_conflict: false,
        conflict: null,
        path_identifier: "test",
      },
    ];

    // WHEN
    const result = buildDiffTreeItems(nodes);

    // THEN
    const treeItems: Array<DiffTreeItem> = [
      {
        id: "TestNode",
        label: "Test Node",
        kind: "TestNode",
        icon: "mdi:tag-multiple",
        isNode: false,
        children: [
          {
            id: "123",
            kind: "TestNode",
            label: "Test Node",
            status: "ADDED",
            hasConflicts: false,
            children: [],
            isNode: true,
          },
        ],
      },
    ];
    expect(result).toEqual(treeItems);
  });

  it("returns tree items for multiple nodes", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "123",
        kind: "TestNode",
        label: "Test Node 1",
        status: "ADDED",
        attributes: [],
        relationships: [],
        contains_conflict: false,
        conflict: null,
        path_identifier: "test1",
      },
      {
        uuid: "456",
        kind: "TestNode",
        label: "Test Node 2",
        status: "UPDATED",
        attributes: [],
        relationships: [],
        contains_conflict: true,
        conflict: null,
        path_identifier: "test2",
      },
    ];

    // WHEN
    const result = buildDiffTreeItems(nodes);

    // THEN
    const treeItems: Array<DiffTreeItem> = [
      {
        id: "TestNode",
        label: "Test Node",
        kind: "TestNode",
        icon: "mdi:tag-multiple",
        isNode: false,
        children: [
          {
            id: "123",
            kind: "TestNode",
            label: "Test Node 1",
            status: "ADDED",
            hasConflicts: false,
            children: [],
            isNode: true,
          },
          {
            id: "456",
            kind: "TestNode",
            label: "Test Node 2",
            status: "UPDATED",
            hasConflicts: true,
            children: [],
            isNode: true,
          },
        ],
      },
    ];
    expect(result).toEqual(treeItems);
  });

  it("groups nodes under top level kind nodes", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "123",
        kind: "TestNode",
        label: "Network 1",
        status: "ADDED",
        attributes: [],
        relationships: [],
        contains_conflict: false,
        conflict: null,
        path_identifier: "network1",
      },
      {
        uuid: "456",
        kind: "TestNode",
        label: "Network 2",
        status: "UPDATED",
        attributes: [],
        relationships: [],
        contains_conflict: false,
        conflict: null,
        path_identifier: "network2",
      },
      {
        uuid: "789",
        kind: "TestNode2",
        label: "Device 1",
        status: "ADDED",
        attributes: [],
        relationships: [],
        contains_conflict: false,
        conflict: null,
        path_identifier: "device1",
      },
    ];

    // WHEN
    const result = buildDiffTreeItems(nodes);

    // THEN
    const treeItems: Array<DiffTreeItem> = [
      {
        id: "TestNode",
        label: "Test Node",
        kind: "TestNode",
        icon: "mdi:tag-multiple",
        isNode: false,
        children: [
          {
            id: "123",
            kind: "TestNode",
            label: "Network 1",
            status: "ADDED",
            hasConflicts: false,
            children: [],
            isNode: true,
          },
          {
            id: "456",
            kind: "TestNode",
            label: "Network 2",
            status: "UPDATED",
            hasConflicts: false,
            children: [],
            isNode: true,
          },
        ],
      },
      {
        id: "TestNode2",
        label: "Test Node 2",
        kind: "TestNode2",
        icon: "mdi:tag-multiple",
        isNode: false,
        children: [
          {
            id: "789",
            kind: "TestNode2",
            label: "Device 1",
            status: "ADDED",
            hasConflicts: false,
            children: [],
            isNode: true,
          },
        ],
      },
    ];
    expect(result).toEqual(treeItems);
  });

  it("returns tree items for nodes with parent relationships", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "123",
        kind: "TestNode",
        label: "Parent Node",
        status: "ADDED",
        attributes: [],
        relationships: [],
        contains_conflict: false,
        conflict: null,
        path_identifier: "parent",
        parent: null,
      },
      {
        uuid: "456",
        kind: "TestNode2",
        label: "Child Node",
        status: "UPDATED",
        attributes: [],
        relationships: [],
        contains_conflict: false,
        conflict: null,
        path_identifier: "child",
        parent: {
          uuid: "123",
          relationship_name: "rel1",
          kind: "TestNode",
        },
      },
    ];

    // WHEN
    const result = buildDiffTreeItems(nodes);

    // THEN
    const treeItems: Array<DiffTreeItem> = [
      {
        id: "TestNode",
        label: "Test Node",
        kind: "TestNode",
        icon: "mdi:tag-multiple",
        isNode: false,
        children: [
          {
            isNode: true,
            id: "123",
            kind: "TestNode",
            label: "Parent Node",
            status: "ADDED",
            hasConflicts: false,
            children: [
              {
                isNode: false,
                id: "123-rel1",
                kind: "TestNode2",
                label: "rel1",
                icon: "mdi:tag-multiple",
                children: [
                  {
                    isNode: true,
                    id: "456",
                    kind: "TestNode2",
                    label: "Child Node",
                    status: "UPDATED",
                    hasConflicts: false,
                    children: [],
                  },
                ],
              },
            ],
          },
        ],
      },
    ];
    expect(result).toEqual(treeItems);
  });
});
