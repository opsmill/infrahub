import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import type { IpPoolAllocation } from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";
import { useGetIpPoolAllocations } from "@/entities/resource-manager/ui/queries/get-ip-pool-allocations.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateIpPoolAllocation,
  generateIpPoolAllocations,
  generateIpPoolResource,
} from "../../../../../../tests/fake/ip-pool";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import {
  IpPoolAllocationsTable,
  type IpPoolAllocationsTableProps,
} from "./ip-pool-allocations-table";

vi.mock("@/entities/resource-manager/ui/queries/get-ip-pool-allocations.query", () => ({
  useGetIpPoolAllocations: vi.fn(),
}));

const resource = generateIpPoolResource();
const initialNodeSchemas = store.get(nodeSchemasAtom);

const mockAllocations = ({
  allocations,
  count = allocations.length,
  hasNextPage = false,
  fetchNextPage = vi.fn(),
}: {
  allocations: IpPoolAllocation[];
  count?: number;
  hasNextPage?: boolean;
  fetchNextPage?: () => void;
}) => {
  vi.mocked(useGetIpPoolAllocations).mockReturnValue({
    data: { pages: [{ count, allocations }], pageParams: [0] },
    error: null,
    isPending: false,
    hasNextPage,
    isFetchingNextPage: false,
    fetchNextPage,
  } as unknown as ReturnType<typeof useGetIpPoolAllocations>);
};

const setIpPrefixSchema = () =>
  store.set(nodeSchemasAtom, [
    generateNodeSchema({
      kind: "IpamIPPrefix",
      name: "IPPrefix",
      namespace: "Ipam",
      label: "IP Prefix",
      inherit_from: [IP_PREFIX_GENERIC],
    }),
  ]);

const renderTable = (props: Partial<IpPoolAllocationsTableProps> = {}) =>
  render(
    <div className="flex h-100 flex-col">
      <IpPoolAllocationsTable
        poolId="pool-id"
        poolKind={IP_PREFIX_POOL}
        resource={resource}
        {...props}
      />
    </div>
  );

describe("IpPoolAllocationsTable", () => {
  beforeEach(() => {
    // react-stately ^3.49 reads process.env.VIRT_ON under NODE_ENV=test, and browser mode has no process global.
    vi.stubGlobal("process", { env: { VIRT_ON: "1" } });
  });

  afterEach(async () => {
    // unmount first, so restoring the schemas does not re-render the component against reset mocks
    await cleanup();
    vi.resetAllMocks();
    vi.unstubAllGlobals();
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("shows the count of allocated prefixes and the resource prefix they come from", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateIpPoolAllocation()], count: 130 });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(
        component.getByRole("heading", { name: "Allocated prefixes" }).element().parentElement
      )
      .toHaveTextContent("Allocated prefixes130in 10.10.0.0/22");
  });

  it("links the resource prefix to its IPAM page", async () => {
    // GIVEN
    setIpPrefixSchema();
    mockAllocations({ allocations: [] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "10.10.0.0/22" }))
      .toHaveAttribute("href", `/ipam/IpamIPPrefix/${resource.id}`);
  });

  it("names the first column Address on an IP address pool", async () => {
    // GIVEN
    mockAllocations({ allocations: [] });

    // WHEN
    const component = await renderTable({ poolKind: IP_ADDRESS_POOL });

    // THEN
    await expect.element(component.getByRole("columnheader", { name: "Address" })).toBeVisible();
  });

  it("links a prefix to its IPAM page and shows its identifier, kind and ID", async () => {
    // GIVEN
    setIpPrefixSchema();
    mockAllocations({
      allocations: [
        generateIpPoolAllocation({
          id: "prefix-id",
          display_label: "10.10.0.0/31",
          identifier: "par1-spine-01__par1-leaf-001__underlay",
        }),
      ],
    });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "10.10.0.0/31" }))
      .toHaveAttribute("href", "/ipam/IpamIPPrefix/prefix-id");
    await expect
      .element(component.getByRole("row", { name: /^10\.10\.0\.0\/31/ }))
      .toHaveTextContent("10.10.0.0/31par1-spine-01__par1-leaf-001__underlayIP Prefixprefix-id");
  });

  it("shows the kind name when the schema is not loaded", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateIpPoolAllocation({ __typename: "IpamIPPrefix" })] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByRole("grid").getByText("IpamIPPrefix")).toBeVisible();
  });

  it("says None for a prefix the pool did not reserve", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateIpPoolAllocation({ identifier: null })] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByRole("grid").getByText("None")).toBeVisible();
  });

  it("says when the resource prefix holds no prefix", async () => {
    // GIVEN
    mockAllocations({ allocations: [] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByText("No prefixes in 10.10.0.0/22 yet")).toBeVisible();
  });

  it("says when the resource prefix holds no address", async () => {
    // GIVEN
    mockAllocations({ allocations: [] });

    // WHEN
    const component = await renderTable({ poolKind: IP_ADDRESS_POOL });

    // THEN
    await expect.element(component.getByText("No addresses in 10.10.0.0/22 yet")).toBeVisible();
  });

  it("shows placeholder rows while the first page loads", async () => {
    // GIVEN
    vi.mocked(useGetIpPoolAllocations).mockReturnValue({
      data: undefined,
      error: null,
      isPending: true,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
    } as unknown as ReturnType<typeof useGetIpPoolAllocations>);

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("status", { name: "Loading allocations" }))
      .toBeVisible();
  });

  it("shows the error when the allocations cannot be read", async () => {
    // GIVEN
    vi.mocked(useGetIpPoolAllocations).mockReturnValue({
      data: undefined,
      error: new Error("Allocations unavailable"),
      isPending: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
    } as unknown as ReturnType<typeof useGetIpPoolAllocations>);

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByText("Allocations unavailable")).toBeVisible();
  });

  it("keeps the loaded rows and offers a retry when loading the next page fails", async () => {
    // GIVEN
    const fetchNextPage = vi.fn();
    vi.mocked(useGetIpPoolAllocations).mockReturnValue({
      data: {
        pages: [
          { count: 2, allocations: [generateIpPoolAllocation({ display_label: "10.10.0.0/31" })] },
        ],
        pageParams: [0],
      },
      error: new Error("Network error"),
      isPending: false,
      hasNextPage: true,
      isFetchingNextPage: false,
      isFetchNextPageError: true,
      fetchNextPage,
    } as unknown as ReturnType<typeof useGetIpPoolAllocations>);

    // WHEN
    const component = await renderTable();
    await component.getByRole("button", { name: "Retry" }).click();

    // THEN
    await expect.element(component.getByRole("row", { name: /^10\.10\.0\.0\/31/ })).toBeVisible();
    await expect
      .element(component.getByRole("alert"))
      .toHaveTextContent("More prefixes could not be loaded.Retry");
    expect(fetchNextPage).toHaveBeenCalledExactlyOnceWith({ cancelRefetch: false });
  });

  it("loads the next rows when the user scrolls to the end", async () => {
    // GIVEN
    const fetchNextPage = vi.fn();
    mockAllocations({
      allocations: generateIpPoolAllocations(40),
      count: 250,
      hasNextPage: true,
      fetchNextPage,
    });
    const component = await renderTable();
    const grid = component.getByRole("grid", { name: "Allocated prefixes" }).element();

    // WHEN
    grid.scrollTop = grid.scrollHeight;
    grid.dispatchEvent(new Event("scroll"));

    // THEN
    await expect.poll(() => fetchNextPage).toHaveBeenCalled();
  });
});
