import { afterEach, describe, expect, it, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../../tests/components/render";
import { generateBranch } from "../../../../../../tests/fake/branch";
import {
  generateIpAddressPoolData,
  generateIpPrefixPoolData,
} from "../../../../../../tests/fake/ip-pool";
import { generatePermission } from "../../../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { IpPoolHeader, IpPoolHeaderSkeleton } from "./ip-pool-header";

const prefixPoolSchema = generateNodeSchema({
  kind: "CoreIPPrefixPool",
  namespace: "Core",
  name: "IPPrefixPool",
  label: "IP Prefix Pool",
});

const renderHeader = (data: IpPoolData, schema: ModelSchema = prefixPoolSchema) =>
  render(<IpPoolHeader pool={data} schema={schema} permission={generatePermission()} />);

describe("IpPoolHeader", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the pool name as the page heading", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData({ name: { value: "PAR1 fabric links" } });

    // WHEN
    const component = await renderHeader(pool);

    // THEN
    await expect
      .element(component.getByRole("heading", { level: 1, name: "PAR1 fabric links" }))
      .toBeVisible();
  });

  it("shows the description when the pool has one", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData({
      description: { value: "Point-to-point links between PAR1 spines and leaves" },
    });

    // WHEN
    const component = await renderHeader(pool);

    // THEN
    await expect
      .element(component.getByText("Point-to-point links between PAR1 spines and leaves"))
      .toBeVisible();
  });

  it("shows the full id with a copy button", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const component = await renderHeader(pool);

    // THEN
    await expect.element(component.getByText(pool.id, { exact: true })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Copy ID" })).toBeVisible();
  });

  it("refreshes the resource manager queries when the refresh button is pressed", async () => {
    // GIVEN
    const invalidateQueriesSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    const pool = generateIpPrefixPoolData();
    const component = await renderHeader(pool);

    // WHEN
    await component.getByRole("button", { name: "Refresh data" }).click();

    // THEN
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ["resource-manager"] });
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({
      queryKey: objectQueryKeys.lists({
        objectKind: pool.__typename,
        branchName: generateBranch().name,
        atDate: null,
      }),
    });
  });

  it("offers the metadata, refresh and actions controls", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const component = await renderHeader(pool);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "View node metadata" }))
      .toBeVisible();
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Actions" })).toBeVisible();
  });

  it("states the namespace and the defaults under the title", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const component = await renderHeader(pool);

    // THEN
    await expect
      .element(component.getByRole("banner"))
      .toMatchTextContent(
        /IP Prefix Pool in namespace default\s*·\s*Prefix kind defaults to IpamIPPrefix\s*·\s*Prefix length defaults to \/31\s*·\s*Member type defaults to Address/
      );
  });
  it("links the actions menu to the prefix pool schema", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();
    const component = await renderHeader(pool);

    // WHEN
    await component.getByRole("button", { name: "Actions" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "View schema" }))
      .toHaveAttribute("href", expect.stringContaining("kind=CoreIPPrefixPool"));
  });

  it("links the actions menu to the address pool schema for an address pool", async () => {
    // GIVEN
    const pool = generateIpAddressPoolData();
    const schema = generateNodeSchema({ kind: "CoreIPAddressPool", documentation: null });
    const component = await renderHeader(pool, schema);

    // WHEN
    await component.getByRole("button", { name: "Actions" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "View schema" }))
      .toHaveAttribute("href", expect.stringContaining("kind=CoreIPAddressPool"));
  });
});

describe("IpPoolHeaderSkeleton", () => {
  it("shows a loading placeholder", async () => {
    // GIVEN
    const skeleton = <IpPoolHeaderSkeleton />;

    // WHEN
    const component = await render(skeleton);

    // THEN
    await expect.element(component.getByRole("status", { name: "Loading IP pool" })).toBeVisible();
  });
});
