import { describe, expect, it } from "vitest";

import type { Permission } from "@/entities/permission/domain/model/permission";
import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../tests/components/utils";
import {
  generateIpAddressPoolData,
  generateIpPrefixPoolData,
} from "../../../../../../tests/fake/ip-pool";
import { generatePermission } from "../../../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { IpPoolActionsMenu } from "./ip-pool-actions-menu";

const prefixPoolSchema = generateNodeSchema({ kind: "CoreIPPrefixPool", documentation: null });

const prefixPool = generateIpPrefixPoolData();

const addressPool = generateIpAddressPoolData();

const MENU_ITEMS = [
  "Copy ID",
  "Copy HFID",
  "Tasks",
  "View schema",
  "GraphQL sandbox",
  "Documentation",
  "Edit",
  "Groups",
  "Delete",
];

const openMenu = async ({
  pool,
  schema = prefixPoolSchema,
  permission = generatePermission(),
  trackPointer = false,
}: {
  pool: IpPoolData;
  schema?: ModelSchema;
  permission?: Permission;
  trackPointer?: boolean;
}) => {
  const component = await render(
    <IpPoolActionsMenu pool={pool} schema={schema} permission={permission} />
  );
  if (trackPointer) await initPointerTracking(component.locator);
  await component.getByRole("button", { name: "Actions" }).click();
  return component;
};

describe("IpPoolActionsMenu", () => {
  it("offers every action to a user with full permission", async () => {
    // WHEN
    const component = await openMenu({
      pool: prefixPool,
      schema: generateNodeSchema({
        kind: "CoreIPPrefixPool",
        documentation: "https://docs.example.com/ip-pools",
      }),
    });

    // THEN
    for (const name of MENU_ITEMS) {
      await expect.element(component.getByRole("menuitem", { name })).toBeVisible();
    }
  });

  it("allows Edit, Groups and Delete with full permission", async () => {
    // WHEN
    const component = await openMenu({ pool: prefixPool });

    // THEN
    for (const name of ["Edit", "Groups", "Delete"]) {
      await expect
        .element(component.getByRole("menuitem", { name }))
        .not.toHaveAttribute("aria-disabled");
    }
  });

  it("hides Documentation when the schema has no documentation link", async () => {
    // WHEN
    const component = await openMenu({ pool: prefixPool });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Documentation" }))
      .not.toBeInTheDocument();
  });

  it("disables Edit, Groups and Delete when the user lacks permission", async () => {
    // WHEN
    const component = await openMenu({
      pool: prefixPool,
      permission: generatePermission({ update: false, delete: false }),
    });

    // THEN
    for (const name of ["Edit", "Groups", "Delete"]) {
      await expect
        .element(component.getByRole("menuitem", { name }))
        .toHaveAttribute("aria-disabled", "true");
    }
  });

  it("explains a missing update permission on Edit", async () => {
    // GIVEN
    const component = await openMenu({
      pool: prefixPool,
      permission: generatePermission({ update: false }),
      trackPointer: true,
    });

    // WHEN
    await component.getByRole("menuitem", { name: "Edit" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "Update not allowed" }))
      .toBeVisible();
  });

  it("explains a missing delete permission on Delete", async () => {
    // GIVEN
    const component = await openMenu({
      pool: prefixPool,
      permission: generatePermission({ delete: false }),
      trackPointer: true,
    });

    // WHEN
    await component.getByRole("menuitem", { name: "Delete" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "Delete not allowed" }))
      .toBeVisible();
  });

  it("links to the prefix pool schema", async () => {
    // WHEN
    const component = await openMenu({ pool: prefixPool });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "View schema" }))
      .toHaveAttribute("href", expect.stringContaining("kind=CoreIPPrefixPool"));
  });

  it("links to the address pool schema for an address pool", async () => {
    // WHEN
    const component = await openMenu({
      pool: addressPool,
      schema: generateNodeSchema({ kind: "CoreIPAddressPool", documentation: null }),
    });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "View schema" }))
      .toHaveAttribute("href", expect.stringContaining("kind=CoreIPAddressPool"));
  });
});
