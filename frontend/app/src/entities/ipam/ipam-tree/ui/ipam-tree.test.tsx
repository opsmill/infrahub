import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { IpNamespaceContext } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import type { IpamTreeNode } from "@/entities/ipam/ipam-tree/domain/model/ipam-tree-node";
import { IpamTree } from "@/entities/ipam/ipam-tree/ui/ipam-tree";
import { useGetIpamTreeNodesByParent } from "@/entities/ipam/ipam-tree/ui/queries/get-ipam-tree-nodes-by-parent.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/entities/ipam/ipam-tree/ui/queries/get-ipam-tree-nodes-by-parent.query");

const PAGE_SIZE = 80;
const TOP_LEVEL = "top-level";

const generateIpamTreeNode = (index: number): IpamTreeNode => ({
  id: `prefix-${index}`,
  display_label: `10.${index}.0.0/16`,
  __typename: "IpamPrefix",
  descendants: { count: 0 },
});

interface TreePages {
  pages: IpamTreeNode[][];
  hasNextPage: boolean;
}

// Keyed by parentObjectId, TOP_LEVEL for the top-level query; unknown parents get no children.
const mockTreePagesByParent = (pagesByParent: Record<string, TreePages>) => {
  vi.mocked(useGetIpamTreeNodesByParent).mockImplementation(({ parentObjectId }) => {
    const { pages, hasNextPage } = pagesByParent[parentObjectId ?? TOP_LEVEL] ?? {
      pages: [],
      hasNextPage: false,
    };
    return {
      data: { pages, pageParams: pages.map((_, index) => index * PAGE_SIZE) },
      isPending: false,
      error: null,
      hasNextPage,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
    } as unknown as ReturnType<typeof useGetIpamTreeNodesByParent>;
  });
};

const ipamTreeInNamespace = (
  <IpNamespaceContext
    value={{
      currentIpNamespace: { id: "namespace-default", __typename: "IpamNamespace" },
      setCurrentIpNamespace: () => {},
    }}
  >
    <IpamTree />
  </IpNamespaceContext>
);

describe("IpamTree", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({
        name: "Prefix",
        namespace: "Ipam",
        kind: "IpamPrefix",
        label: "Prefix",
        display_label: "prefix__value",
      }),
    ]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test.each([
    { position: "last", repeatedIndex: PAGE_SIZE - 1 },
    { position: "middle", repeatedIndex: PAGE_SIZE / 2 },
  ])(
    "keeps rendering every prefix once when the next page repeats the $position prefix already shown",
    async ({ repeatedIndex }) => {
      // GIVEN
      const firstPage = Array.from({ length: PAGE_SIZE }, (_, index) =>
        generateIpamTreeNode(index)
      );
      mockTreePagesByParent({ [TOP_LEVEL]: { pages: [firstPage], hasNextPage: true } });
      const component = await render(ipamTreeInNamespace);
      await expect.element(component.getByText("10.79.0.0/16")).toBeInTheDocument();

      // WHEN
      mockTreePagesByParent({
        [TOP_LEVEL]: {
          pages: [firstPage, [generateIpamTreeNode(repeatedIndex)]],
          hasNextPage: false,
        },
      });
      await component.rerender(ipamTreeInNamespace);

      // THEN
      await expect
        .element(component.getByRole("treegrid", { name: "IPAM tree" }))
        .toBeInTheDocument();
      expect(component.getByRole("row").elements()).toHaveLength(PAGE_SIZE);
      expect(component.getByText(`10.${repeatedIndex}.0.0/16`).elements()).toHaveLength(1);
    }
  );

  test("keeps rendering every child prefix once when the next page of children repeats the last child already shown", async () => {
    // GIVEN
    const parentPrefix: IpamTreeNode = {
      id: "parent-prefix",
      display_label: "10.0.0.0/8",
      __typename: "IpamPrefix",
      descendants: { count: PAGE_SIZE },
    };
    const firstChildrenPage = Array.from({ length: PAGE_SIZE }, (_, index) =>
      generateIpamTreeNode(index)
    );
    const topLevelPages = { pages: [[parentPrefix]], hasNextPage: false };
    mockTreePagesByParent({
      [TOP_LEVEL]: topLevelPages,
      [parentPrefix.id]: { pages: [firstChildrenPage], hasNextPage: true },
    });
    const component = await render(ipamTreeInNamespace);
    await component.getByRole("button", { name: /^Expand/ }).click();
    await expect.element(component.getByText("10.79.0.0/16")).toBeInTheDocument();

    // WHEN
    mockTreePagesByParent({
      [TOP_LEVEL]: topLevelPages,
      [parentPrefix.id]: {
        pages: [firstChildrenPage, [generateIpamTreeNode(PAGE_SIZE - 1)]],
        hasNextPage: false,
      },
    });
    await component.rerender(ipamTreeInNamespace);

    // THEN
    await expect
      .element(component.getByRole("treegrid", { name: "IPAM tree" }))
      .toBeInTheDocument();
    expect(component.getByRole("row").elements()).toHaveLength(PAGE_SIZE + 1);
    expect(component.getByText("10.79.0.0/16").elements()).toHaveLength(1);
  });
});
