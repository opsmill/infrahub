import { describe, it, expect } from "vitest";
import { formatDiffNodesToDiffTree } from "../../../../src/screens/diff/diff-tree";
import { DiffNode } from "../../../../src/screens/diff/node-diff/types";
import { TREE_ROOT_ID } from "../../../../src/screens/ipam/constants";

describe("Format diff nodes to diff tree", () => {
  it("should return an empty array when no nodes are provided", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [];

    // WHEN
    const result = formatDiffNodesToDiffTree(nodes);

    // THEN
    expect(result).toEqual([]);
  });

  it("should handle a single node correctly", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "1",
        label: "Node 1",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode",
        path_identifier: "node1",
        status: "ADDED",
      },
    ];

    // WHEN
    const result = formatDiffNodesToDiffTree(nodes);

    // THEN
    expect(result).toEqual([
      {
        id: "1",
        name: "Node 1",
        parent: TREE_ROOT_ID,
        children: [],
        metadata: {
          uuid: "1",
          kind: "TestNode",
          status: "ADDED",
          containsConflicts: false,
        },
      },
    ]);
  });

  it("should handle multiple nodes correctly", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "1",
        label: "Node 1",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode",
        path_identifier: "node1",
        status: "ADDED",
      },
      {
        uuid: "2",
        label: "Node 2",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode",
        path_identifier: "node2",
        status: "UPDATED",
      },
    ];

    // WHEN
    const result = formatDiffNodesToDiffTree(nodes);

    // THEN
    expect(result).toEqual([
      {
        id: "1",
        name: "Node 1",
        parent: TREE_ROOT_ID,
        children: [],
        metadata: {
          uuid: "1",
          kind: "TestNode",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "2",
        name: "Node 2",
        parent: TREE_ROOT_ID,
        children: [],
        metadata: {
          uuid: "2",
          kind: "TestNode",
          status: "UPDATED",
          containsConflicts: false,
        },
      },
    ]);
  });

  it("should handle nodes with parent correctly", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "1",
        label: "Node 1",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode",
        path_identifier: "node1",
        status: "ADDED",
      },
      {
        uuid: "2",
        label: "Node 2",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode",
        path_identifier: "node2",
        status: "UPDATED",
        parent: {
          uuid: "1",
          kind: "TestNode",
          relationship_name: "relationshipAB",
        },
      },
    ];

    // WHEN
    const result = formatDiffNodesToDiffTree(nodes);

    // THEN
    expect(result).toEqual([
      {
        id: "1",
        name: "Node 1",
        parent: TREE_ROOT_ID,
        children: ["1relationshipAB"],
        metadata: {
          uuid: "1",
          kind: "TestNode",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "1relationshipAB",
        name: "relationshipAB",
        parent: "1",
        children: ["2"],
        metadata: {
          kind: "TestNode",
        },
      },
      {
        id: "2",
        name: "Node 2",
        parent: "1relationshipAB",
        children: [],
        metadata: {
          uuid: "2",
          kind: "TestNode",
          status: "UPDATED",
          containsConflicts: false,
        },
      },
    ]);
  });

  it("should handle nodes with the same parent correctly", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "1",
        label: "Node 1",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode",
        path_identifier: "node1",
        status: "ADDED",
      },
      {
        uuid: "2",
        label: "Node 2",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode",
        path_identifier: "node2",
        status: "UPDATED",
        parent: {
          uuid: "1",
          kind: "TestNode",
          relationship_name: "relationshipAB",
        },
      },
      {
        uuid: "3",
        label: "Node 3",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode",
        path_identifier: "node3",
        status: "UPDATED",
        parent: {
          uuid: "1",
          kind: "TestNode",
          relationship_name: "relationshipAB",
        },
      },
    ];

    // WHEN
    const result = formatDiffNodesToDiffTree(nodes);

    // THEN
    expect(result).toEqual([
      {
        id: "1",
        name: "Node 1",
        parent: TREE_ROOT_ID,
        children: ["1relationshipAB"],
        metadata: {
          uuid: "1",
          kind: "TestNode",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "1relationshipAB",
        name: "relationshipAB",
        parent: "1",
        children: ["2", "3"],
        metadata: {
          kind: "TestNode",
        },
      },
      {
        id: "2",
        name: "Node 2",
        parent: "1relationshipAB",
        children: [],
        metadata: {
          uuid: "2",
          kind: "TestNode",
          status: "UPDATED",
          containsConflicts: false,
        },
      },
      {
        id: "3",
        name: "Node 3",
        parent: "1relationshipAB",
        children: [],
        metadata: {
          uuid: "3",
          kind: "TestNode",
          status: "UPDATED",
          containsConflicts: false,
        },
      },
    ]);
  });

  it("should handle nodes with different parents correctly", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "1",
        label: "Node 1",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode1",
        path_identifier: "node1",
        status: "ADDED",
        parent: null,
      },
      {
        uuid: "2",
        label: "Node 2",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode2",
        path_identifier: "node2",
        status: "ADDED",
        parent: {
          uuid: "1",
          kind: "TestNode1",
          relationship_name: "relationship12",
        },
      },
      {
        uuid: "3",
        label: "Node 3",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode3",
        path_identifier: "node3",
        status: "ADDED",
        parent: null,
      },
      {
        uuid: "4",
        label: "Node 4",
        attributes: [],
        relationships: [],
        conflict: {} as any,
        contains_conflict: true,
        kind: "TestNode4",
        path_identifier: "node4",
        status: "REMOVED",
        parent: {
          uuid: "3",
          kind: "TestNode3",
          relationship_name: "relationship34",
        },
      },
    ];

    // WHEN
    const result = formatDiffNodesToDiffTree(nodes);

    // THEN
    expect(result).toEqual([
      {
        id: "1",
        name: "Node 1",
        parent: TREE_ROOT_ID,
        children: ["1relationship12"],
        metadata: {
          uuid: "1",
          kind: "TestNode1",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "1relationship12",
        name: "relationship12",
        parent: "1",
        children: ["2"],
        metadata: {
          kind: "TestNode1",
        },
      },
      {
        id: "2",
        name: "Node 2",
        parent: "1relationship12",
        children: [],
        metadata: {
          uuid: "2",
          kind: "TestNode2",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "3",
        name: "Node 3",
        parent: TREE_ROOT_ID,
        children: ["3relationship34"],
        metadata: {
          uuid: "3",
          kind: "TestNode3",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "3relationship34",
        name: "relationship34",
        parent: "3",
        children: ["4"],
        metadata: {
          kind: "TestNode3",
        },
      },
      {
        id: "4",
        name: "Node 4",
        parent: "3relationship34",
        children: [],
        metadata: {
          uuid: "4",
          kind: "TestNode4",
          status: "REMOVED",
          containsConflicts: true,
        },
      },
    ]);
  });

  it("should handle nested children correctly", () => {
    // GIVEN
    const nodes: Array<DiffNode> = [
      {
        uuid: "1",
        label: "Node 1",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode1",
        path_identifier: "node1",
        status: "ADDED",
        parent: null,
      },
      {
        uuid: "2",
        label: "Node 2",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode2",
        path_identifier: "node2",
        status: "ADDED",
        parent: {
          uuid: "1",
          kind: "TestNode1",
          relationship_name: "relationship12",
        },
      },
      {
        uuid: "3",
        label: "Node 3",
        attributes: [],
        relationships: [],
        conflict: null,
        contains_conflict: false,
        kind: "TestNode3",
        path_identifier: "node3",
        status: "ADDED",
        parent: {
          uuid: "2",
          kind: "TestNode2",
          relationship_name: "relationship23",
        },
      },
      {
        uuid: "4",
        label: "Node 4",
        attributes: [],
        relationships: [],
        conflict: {} as any,
        contains_conflict: true,
        kind: "TestNode4",
        path_identifier: "node4",
        status: "REMOVED",
        parent: {
          uuid: "3",
          kind: "TestNode3",
          relationship_name: "relationship34",
        },
      },
    ];

    // WHEN
    const result = formatDiffNodesToDiffTree(nodes);

    // THEN
    expect(result).toEqual([
      {
        id: "1",
        name: "Node 1",
        parent: TREE_ROOT_ID,
        children: ["1relationship12"],
        metadata: {
          uuid: "1",
          kind: "TestNode1",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "1relationship12",
        name: "relationship12",
        parent: "1",
        children: ["2"],
        metadata: {
          kind: "TestNode1",
        },
      },
      {
        id: "2",
        name: "Node 2",
        parent: "1relationship12",
        children: ["2relationship23"],
        metadata: {
          uuid: "2",
          kind: "TestNode2",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "2relationship23",
        name: "relationship23",
        parent: "2",
        children: ["3"],
        metadata: {
          kind: "TestNode2",
        },
      },
      {
        id: "3",
        name: "Node 3",
        parent: "2relationship23",
        children: ["3relationship34"],
        metadata: {
          uuid: "3",
          kind: "TestNode3",
          status: "ADDED",
          containsConflicts: false,
        },
      },
      {
        id: "3relationship34",
        name: "relationship34",
        parent: "3",
        children: ["4"],
        metadata: {
          kind: "TestNode3",
        },
      },
      {
        id: "4",
        name: "Node 4",
        parent: "3relationship34",
        children: [],
        metadata: {
          uuid: "4",
          kind: "TestNode4",
          status: "REMOVED",
          containsConflicts: true,
        },
      },
    ]);
  });
});
