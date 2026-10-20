import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import {
  GetTreeNodesByParentFromApi,
  type GetTreeNodesByParentFromApiParams,
} from "@/entities/nodes/hierarchy/api/get-tree-nodes-by-parent-from-api";
import { ObjectHierarchyTree } from "@/entities/nodes/hierarchy/ui/object-hierarchy-tree";
import type { NodeCoreWithChildrenCount } from "@/entities/nodes/object/domain/model/node";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateGenericSchema, generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/entities/nodes/hierarchy/api/get-tree-nodes-by-parent-from-api");

const LOCATION_SCHEMA = generateGenericSchema({
  kind: "LocationGeneric",
  namespace: "Location",
  name: "Generic",
  label: "Location",
});

function buildTreeNode(
  id: string,
  kind: string,
  displayLabel: string,
  childrenCount: number
): NodeCoreWithChildrenCount {
  return {
    id,
    __typename: kind,
    display_label: displayLabel,
    hfid: null,
    children: { count: childrenCount },
  };
}

// Belgium is listed under both Europe and Americas.
const NODES_BY_PARENT_ID = new Map<string | null, Array<NodeCoreWithChildrenCount>>([
  [
    null,
    [
      buildTreeNode("europe-id", "LocationRegion", "Europe", 2),
      buildTreeNode("americas-id", "LocationRegion", "Americas", 2),
    ],
  ],
  [
    "europe-id",
    [
      buildTreeNode("belgium-id", "LocationCountry", "Belgium", 0),
      buildTreeNode("france-id", "LocationCountry", "France", 0),
    ],
  ],
  [
    "americas-id",
    [
      buildTreeNode("belgium-id", "LocationCountry", "Belgium", 0),
      buildTreeNode("brazil-id", "LocationCountry", "Brazil", 0),
    ],
  ],
]);

function mockTreeNodes({ parentObjectId }: GetTreeNodesByParentFromApiParams) {
  const nodes = NODES_BY_PARENT_ID.get(parentObjectId ?? null) ?? [];
  return Promise.resolve({
    data: { LocationGeneric: { edges: nodes.map((node) => ({ node })) } },
  } as unknown as Awaited<ReturnType<typeof GetTreeNodesByParentFromApi>>);
}

describe("ObjectHierarchyTree", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({ kind: "LocationRegion", namespace: "Location", name: "Region" }),
      generateNodeSchema({ kind: "LocationCountry", namespace: "Location", name: "Country" }),
    ]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("lists an object under each of its parents when it has two", async () => {
    // GIVEN
    vi.mocked(GetTreeNodesByParentFromApi).mockImplementation(mockTreeNodes);
    const component = await render(<ObjectHierarchyTree treeSchema={LOCATION_SCHEMA} />);
    await component.getByRole("row", { name: "Europe" }).getByRole("button").click();
    await expect.element(component.getByRole("row", { name: "France" })).toBeVisible();

    // WHEN
    await component.getByRole("row", { name: "Americas" }).getByRole("button").click();

    // THEN
    await expect.element(component.getByRole("row", { name: "Brazil" })).toBeVisible();
    await expect
      .poll(() =>
        component
          .getByRole("row")
          .elements()
          .map((row) => row.textContent)
      )
      .toEqual(["Europe", "Belgium", "France", "Americas", "Belgium", "Brazil"]);
  });
});
