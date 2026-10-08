import { describe, expect, it } from "vitest";

import type { Permission } from "@/entities/permission/domain/model/permission";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import { generateNumberPoolData } from "../../../../../tests/fake/number-pool";
import { generatePermission } from "../../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { NumberPoolActionsMenu } from "./number-pool-actions-menu";

const numberPoolSchema = generateNodeSchema({ kind: "CoreNumberPool", documentation: null });

const userPool = generateNumberPoolData();

const schemaPool = generateNumberPoolData({ pool_type: { value: "Schema" } });

const SCHEMA_LOCK = "Defined by the schema attribute InfraInterface.speed";

const openMenu = async ({
  pool,
  schema = numberPoolSchema,
  permission = generatePermission(),
  trackPointer = false,
}: {
  pool: NumberPoolData;
  schema?: ModelSchema;
  permission?: Permission;
  trackPointer?: boolean;
}) => {
  const component = await render(
    <NumberPoolActionsMenu pool={pool} schema={schema} permission={permission} />
  );
  if (trackPointer) await initPointerTracking(component.locator);
  await component.getByRole("button", { name: "Actions" }).click();
  return component;
};

describe("NumberPoolActionsMenu", () => {
  it("locks Edit and Delete on a schema-created pool and keeps Groups available", async () => {
    // WHEN
    const component = await openMenu({ pool: schemaPool });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Edit" }))
      .toHaveAttribute("aria-disabled", "true");
    await expect
      .element(component.getByRole("menuitem", { name: "Delete" }))
      .toHaveAttribute("aria-disabled", "true");
    await expect
      .element(component.getByRole("menuitem", { name: "Groups" }))
      .not.toHaveAttribute("aria-disabled");
  });

  it("explains the schema lock on a locked item", async () => {
    // GIVEN
    const component = await openMenu({ pool: schemaPool, trackPointer: true });

    // WHEN
    await component.getByRole("menuitem", { name: "Edit" }).hover();

    // THEN
    await expect.element(component.getByRole("tooltip", { name: SCHEMA_LOCK })).toBeVisible();
  });

  it("links to the number pool schema", async () => {
    // WHEN
    const component = await openMenu({ pool: userPool });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "View schema" }))
      .toHaveAttribute("href", "/schema?kind=CoreNumberPool");
  });

  it("allows every action on a user-created pool with full permission", async () => {
    // WHEN
    const component = await openMenu({ pool: userPool });

    // THEN
    for (const name of ["Edit", "Groups", "Delete"]) {
      await expect
        .element(component.getByRole("menuitem", { name }))
        .not.toHaveAttribute("aria-disabled");
    }
  });

  it("disables Edit, Groups and Delete when the user lacks permission", async () => {
    // WHEN
    const component = await openMenu({
      pool: userPool,
      permission: generatePermission({ update: false, delete: false }),
    });

    // THEN
    for (const name of ["Edit", "Groups", "Delete"]) {
      await expect
        .element(component.getByRole("menuitem", { name }))
        .toHaveAttribute("aria-disabled", "true");
    }
  });

  it("explains the schema lock before a missing permission", async () => {
    // GIVEN
    const component = await openMenu({
      pool: schemaPool,
      permission: generatePermission({ update: false, delete: false }),
      trackPointer: true,
    });

    // WHEN
    await component.getByRole("menuitem", { name: "Delete" }).hover();

    // THEN
    await expect.element(component.getByRole("tooltip", { name: SCHEMA_LOCK })).toBeVisible();
  });

  it("links to the documentation when the schema has a documentation link", async () => {
    // WHEN
    const component = await openMenu({
      pool: userPool,
      schema: generateNodeSchema({
        kind: "CoreNumberPool",
        documentation: "https://docs.example.com/number-pools",
      }),
    });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Documentation" }))
      .toHaveAttribute("href", "https://docs.example.com/number-pools");
  });

  it("hides Documentation when the schema has no documentation link", async () => {
    // WHEN
    const component = await openMenu({ pool: userPool });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Documentation" }))
      .not.toBeInTheDocument();
  });

  it("hides Copy HFID when the pool has no HFID", async () => {
    // WHEN
    const component = await openMenu({ pool: { ...userPool, hfid: null } });

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Copy ID" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Copy HFID" }))
      .not.toBeInTheDocument();
  });
});
