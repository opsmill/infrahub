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

const generateIpamTreeNode = (index: number): IpamTreeNode => ({
  id: `prefix-${index}`,
  display_label: `10.${index}.0.0/16`,
  __typename: "IpamPrefix",
  descendants: { count: 0 },
});

const mockTreePages = (pages: IpamTreeNode[][], hasNextPage: boolean) => {
  vi.mocked(useGetIpamTreeNodesByParent).mockReturnValue({
    data: { pages, pageParams: pages.map((_, index) => index * PAGE_SIZE) },
    isPending: false,
    error: null,
    hasNextPage,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
  } as unknown as ReturnType<typeof useGetIpamTreeNodesByParent>);
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

  test("keeps rendering every prefix once when the next page repeats the last prefix already shown", async () => {
    // GIVEN
    const firstPage = Array.from({ length: PAGE_SIZE }, (_, index) => generateIpamTreeNode(index));
    mockTreePages([firstPage], true);
    const component = await render(ipamTreeInNamespace);
    await expect.element(component.getByText("10.79.0.0/16")).toBeInTheDocument();

    // WHEN
    mockTreePages([firstPage, [generateIpamTreeNode(PAGE_SIZE - 1)]], false);
    await component.rerender(ipamTreeInNamespace);

    // THEN
    await expect
      .element(component.getByRole("treegrid", { name: "IPAM tree" }))
      .toBeInTheDocument();
    expect(component.getByRole("row").elements()).toHaveLength(PAGE_SIZE);
    expect(component.getByText("10.79.0.0/16").elements()).toHaveLength(1);
  });
});
