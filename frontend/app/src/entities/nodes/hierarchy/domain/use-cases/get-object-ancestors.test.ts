import { describe, expect, it, vi } from "vitest";

import * as getObjectAncestorsFromApiModule from "@/entities/nodes/hierarchy/api/get-object-ancestors-from-api";
import type { NodeCoreWithParent } from "@/entities/nodes/object/domain/model/node";

import { getObjectAncestors } from "./get-object-ancestors";

vi.mock("@/entities/nodes/hierarchy/api/get-object-ancestors-from-api");

describe("getObjectAncestors", () => {
  const branchName = "main";
  const objectKind = "LocationCity";
  const objectId = "city-id";

  it("should return ancestors ordered from root (parent=null) to current object", async () => {
    // GIVEN: A hierarchy where grandparent -> parent -> child -> grandchild
    // API returns them in unordered fashion: [child, grandchild, parent, grandparent]
    const grandparent: NodeCoreWithParent = {
      id: "grandparent-id",
      __typename: "LocationCountry",
      display_label: "USA",
      parent: { node: null },
    };

    const parent: NodeCoreWithParent = {
      id: "parent-id",
      __typename: "LocationState",
      display_label: "California",
      parent: {
        node: { id: "grandparent-id", __typename: "LocationCountry", display_label: "USA" },
      },
    };

    const child: NodeCoreWithParent = {
      id: "child-id",
      __typename: "LocationCity",
      display_label: "Los Angeles",
      parent: {
        node: { id: "parent-id", __typename: "LocationState", display_label: "California" },
      },
    };

    const grandchild: NodeCoreWithParent = {
      id: "grandchild-id",
      __typename: "LocationNeighborhood",
      display_label: "Hollywood",
      parent: {
        node: { id: "child-id", __typename: "LocationCity", display_label: "Los Angeles" },
      },
    };

    // Simulate unordered response from API
    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [
            {
              node: {
                ...grandchild,
                ancestors: {
                  edges: [
                    { node: child },
                    { node: grandparent }, // Not in order
                    { node: parent },
                  ],
                },
              },
            },
          ],
        },
      },
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN
    const result = await getObjectAncestors({
      branchName,
      objectKind,
      objectId,
    });

    // THEN: Should be ordered from root to leaf
    expect(result.chain.map((node) => node.id)).toEqual([
      "grandparent-id",
      "parent-id",
      "child-id",
      "grandchild-id",
    ]);
    expect(result.chain.map((node) => node.display_label)).toEqual([
      "USA",
      "California",
      "Los Angeles",
      "Hollywood",
    ]);
    expect(result.otherAncestors).toEqual([]);
  });

  it("should handle a single object with no ancestors", async () => {
    // GIVEN: An object with no ancestors (root node)
    const rootNode: NodeCoreWithParent = {
      id: "root-id",
      __typename: "LocationCountry",
      display_label: "USA",
      parent: { node: null },
    };

    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [
            {
              node: {
                ...rootNode,
                ancestors: {
                  edges: [],
                },
              },
            },
          ],
        },
      },
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN
    const result = await getObjectAncestors({
      branchName,
      objectKind,
      objectId,
    });

    // THEN: Should return just the root node
    expect(result.chain.map((node) => node.id)).toEqual(["root-id"]);
    expect(result.chain.map((node) => node.display_label)).toEqual(["USA"]);
    expect(result.otherAncestors).toEqual([]);
  });

  it("should handle a two-level hierarchy (parent -> child)", async () => {
    // GIVEN: A simple parent-child relationship
    const parent: NodeCoreWithParent = {
      id: "parent-id",
      __typename: "LocationCountry",
      display_label: "USA",
      parent: { node: null },
    };

    const child: NodeCoreWithParent = {
      id: "child-id",
      __typename: "LocationState",
      display_label: "California",
      parent: { node: { id: "parent-id", __typename: "LocationCountry", display_label: "USA" } },
    };

    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [
            {
              node: {
                ...child,
                ancestors: {
                  edges: [{ node: parent }],
                },
              },
            },
          ],
        },
      },
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN
    const result = await getObjectAncestors({
      branchName,
      objectKind,
      objectId,
    });

    // THEN: Should be ordered parent first, then child
    expect(result.chain.map((node) => node.id)).toEqual(["parent-id", "child-id"]);
    expect(result.chain.map((node) => node.display_label)).toEqual(["USA", "California"]);
    expect(result.otherAncestors).toEqual([]);
  });

  it("should throw an error when object is not found", async () => {
    // GIVEN: API returns no results
    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [],
        },
      },
      errors: null,
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN/THEN
    await expect(
      getObjectAncestors({
        branchName,
        objectKind,
        objectId,
      })
    ).rejects.toThrow(`Cannot find ${objectKind} with id ${objectId}`);
  });

  it("should throw an error when API returns errors", async () => {
    // GIVEN: API returns errors
    const mockApiResponse = {
      data: null,
      errors: [{ message: "GraphQL error 1" }, { message: "GraphQL error 2" }],
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN/THEN
    await expect(
      getObjectAncestors({
        branchName,
        objectKind,
        objectId,
      })
    ).rejects.toThrow("GraphQL error 1; GraphQL error 2");
  });

  it("should handle ancestors with undefined edges", async () => {
    // GIVEN: An object where ancestors have undefined edges
    const rootNode: NodeCoreWithParent = {
      id: "root-id",
      __typename: "LocationCountry",
      display_label: "USA",
      parent: { node: null },
    };

    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [
            {
              node: {
                ...rootNode,
                ancestors: {
                  edges: undefined,
                },
              },
            },
          ],
        },
      },
      errors: null,
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN
    const result = await getObjectAncestors({
      branchName,
      objectKind,
      objectId,
    });

    // THEN: Should handle gracefully and return just the current node
    expect(result.chain.map((node) => node.id)).toEqual(["root-id"]);
    expect(result.otherAncestors).toEqual([]);
  });

  it("should handle ancestors with null nodes in edges", async () => {
    // GIVEN: An object where some ancestor edges have null nodes
    const parent: NodeCoreWithParent = {
      id: "parent-id",
      __typename: "LocationCountry",
      display_label: "USA",
      parent: { node: null },
    };

    const child: NodeCoreWithParent = {
      id: "child-id",
      __typename: "LocationState",
      display_label: "California",
      parent: { node: { id: "parent-id", __typename: "LocationCountry", display_label: "USA" } },
    };

    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [
            {
              node: {
                ...child,
                ancestors: {
                  edges: [{ node: null }, { node: parent }, { node: null }],
                },
              },
            },
          ],
        },
      },
      errors: null,
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN
    const result = await getObjectAncestors({
      branchName,
      objectKind,
      objectId,
    });

    // THEN: Should filter out null nodes and still maintain order
    expect(result.chain.map((node) => node.id)).toEqual(["parent-id", "child-id"]);
    expect(result.otherAncestors).toEqual([]);
  });

  it("should return partial ancestors chain when root is missing from response", async () => {
    // GIVEN
    const child: NodeCoreWithParent = {
      id: "child-id",
      __typename: "LocationCity",
      display_label: "Los Angeles",
      parent: {
        node: { id: "parent-id", __typename: "LocationState", display_label: "California" },
      },
    };
    const parent: NodeCoreWithParent = {
      id: "parent-id",
      __typename: "LocationState",
      display_label: "California",
      parent: {
        node: { id: "grandparent-id", __typename: "LocationCountry", display_label: "USA" },
      },
    };
    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [
            {
              node: {
                ...child,
                ancestors: {
                  edges: [{ node: parent }],
                },
              },
            },
          ],
        },
      },
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN
    const result = await getObjectAncestors({
      branchName,
      objectKind,
      objectId,
    });

    // THEN
    expect(result.chain.map((node) => node.id)).toEqual(["parent-id", "child-id"]);
    expect(result.otherAncestors).toEqual([]);
  });

  it("should list the ancestors outside the chain when the object has a second parent", async () => {
    // GIVEN: The object's parent is Europe, but the API also returns Americas as an ancestor
    const europe: NodeCoreWithParent = {
      id: "europe-id",
      __typename: "LocationRegion",
      display_label: "Europe",
      parent: { node: null },
    };
    const americas: NodeCoreWithParent = {
      id: "americas-id",
      __typename: "LocationRegion",
      display_label: "Americas",
      parent: { node: null },
    };
    const belgium: NodeCoreWithParent = {
      id: "belgium-id",
      __typename: "LocationCountry",
      display_label: "Belgium",
      parent: { node: { id: "europe-id", __typename: "LocationRegion", display_label: "Europe" } },
    };

    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [
            {
              node: {
                ...belgium,
                ancestors: {
                  edges: [{ node: americas }, { node: europe }],
                },
              },
            },
          ],
        },
      },
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN
    const result = await getObjectAncestors({
      branchName,
      objectKind,
      objectId,
    });

    // THEN
    expect(result.chain.map((node) => node.id)).toEqual(["europe-id", "belgium-id"]);
    expect(result.otherAncestors.map((node) => node.display_label)).toEqual(["Americas"]);
  });

  it("should stop following parents when they loop back", async () => {
    // GIVEN: Paris is in France, and France and Europe are each other's parent
    const europe: NodeCoreWithParent = {
      id: "europe-id",
      __typename: "LocationRegion",
      display_label: "Europe",
      parent: { node: { id: "france-id", __typename: "LocationCountry", display_label: "France" } },
    };
    const france: NodeCoreWithParent = {
      id: "france-id",
      __typename: "LocationCountry",
      display_label: "France",
      parent: { node: { id: "europe-id", __typename: "LocationRegion", display_label: "Europe" } },
    };
    const paris: NodeCoreWithParent = {
      id: "paris-id",
      __typename: "LocationCity",
      display_label: "Paris",
      parent: { node: { id: "france-id", __typename: "LocationCountry", display_label: "France" } },
    };

    const mockApiResponse = {
      data: {
        [objectKind]: {
          edges: [
            {
              node: {
                ...paris,
                ancestors: {
                  edges: [{ node: europe }, { node: france }],
                },
              },
            },
          ],
        },
      },
    };

    vi.mocked(getObjectAncestorsFromApiModule.getObjectAncestorsFromApi).mockResolvedValue(
      mockApiResponse as any
    );

    // WHEN
    const result = await getObjectAncestors({
      branchName,
      objectKind,
      objectId,
    });

    // THEN
    expect(result.chain.map((node) => node.id)).toEqual(["europe-id", "france-id", "paris-id"]);
    expect(result.otherAncestors).toEqual([]);
  });
});
