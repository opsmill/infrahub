import { describe, expect, it, vi } from "vitest";

import type { NodeCoreWithParent } from "@/entities/nodes/types";

import * as getObjectAncestorsFromApiModule from "../api/get-object-ancestors-from-api";
import { getObjectAncestors } from "./get-object-ancestors";

vi.mock("../api/get-object-ancestors-from-api");

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
    expect(result).toHaveLength(4);
    expect(result[0]!.id).toBe("grandparent-id");
    expect(result[0]!.display_label).toBe("USA");
    expect(result[1]!.id).toBe("parent-id");
    expect(result[1]!.display_label).toBe("California");
    expect(result[2]!.id).toBe("child-id");
    expect(result[2]!.display_label).toBe("Los Angeles");
    expect(result[3]!.id).toBe("grandchild-id");
    expect(result[3]!.display_label).toBe("Hollywood");
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
    expect(result).toHaveLength(1);
    expect(result[0]!.id).toBe("root-id");
    expect(result[0]!.display_label).toBe("USA");
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
    expect(result).toHaveLength(2);
    expect(result[0]!.id).toBe("parent-id");
    expect(result[0]!.display_label).toBe("USA");
    expect(result[1]!.id).toBe("child-id");
    expect(result[1]!.display_label).toBe("California");
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
    expect(result).toHaveLength(1);
    expect(result[0]!.id).toBe("root-id");
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
    expect(result[1]!.id).toBe("child-id");
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
    expect(result).toHaveLength(2);
    expect(result[0]!.id).toBe("parent-id");
    expect(result[1]!.id).toBe("child-id");
  });
});
