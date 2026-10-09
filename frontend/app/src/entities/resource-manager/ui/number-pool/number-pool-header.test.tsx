import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateNumberPoolData } from "../../../../../tests/fake/number-pool";
import { generatePermission } from "../../../../../tests/fake/permission";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import { NumberPoolHeader, NumberPoolHeaderSkeleton } from "./number-pool-header";

vi.mock("@/entities/resource-manager/ui/number-pool/number-pool-actions-menu", () => ({
  NumberPoolActionsMenu: () => <button type="button">Actions</button>,
}));

const initialNodeSchemas = store.get(nodeSchemasAtom);

const numberPoolSchema = generateNodeSchema({
  kind: "CoreNumberPool",
  namespace: "Core",
  name: "NumberPool",
});

const interfaceSchema = generateNodeSchema({
  kind: "InfraInterface",
  namespace: "Infra",
  name: "Interface",
  label: "Interface",
  attributes: [
    generateAttributeSchema({ id: "speed-attribute-id", name: "speed", label: "Speed" }),
    generateAttributeSchema({ name: "role", label: "Role" }),
  ],
  relationships: [generateRelationshipSchema({ name: "site", label: "Site" })],
});

const schemaPool = generateNumberPoolData({
  id: "18a4f2c0-7b1e-4c55-9d2a-0f3e6b8c1d27",
  hfid: ["InfraInterface.speed [18a4f2c0-7b1e-4c55-9d2a-0f3e6b8c1d27]"],
  name: { value: "InfraInterface.speed [18a4f2c0-7b1e-4c55-9d2a-0f3e6b8c1d27]" },
  pool_type: { value: "Schema" },
});

const userPool = generateNumberPoolData({
  description: { value: "Speeds handed out to new interfaces" },
  allocation_scope: { value: ["site", "role"] },
});

const renderHeader = (pool: NumberPoolData) =>
  render(
    <NumberPoolHeader pool={pool} schema={numberPoolSchema} permission={generatePermission()} />
  );

describe("NumberPoolHeader", () => {
  beforeAll(() => {
    store.set(nodeSchemasAtom, [numberPoolSchema, interfaceSchema]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("shows the pool name as the page heading", async () => {
    // WHEN
    const component = await renderHeader(userPool);

    // THEN
    await expect
      .element(component.getByRole("heading", { level: 1, name: "Interface speeds" }))
      .toBeVisible();
  });

  it("tags a schema-created pool as managed by schema", async () => {
    // WHEN
    const component = await renderHeader(schemaPool);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Managed by schema" }))
      .toBeVisible();
  });

  it("opens the attribute that created a schema pool in a modal", async () => {
    // GIVEN
    const component = await renderHeader(schemaPool);

    // WHEN
    await component.getByRole("button", { name: "Managed by schema" }).click();

    // THEN
    await expect.element(component.getByRole("dialog", { name: "Schema viewer" })).toBeVisible();
    await expect.element(component.getByText("speed-attribute-id")).toBeVisible();
  });

  it("shows no managed-by tag for a user-created pool", async () => {
    // WHEN
    const component = await renderHeader(userPool);

    // THEN
    await expect.element(component.getByText(/Managed by/)).not.toBeInTheDocument();
  });

  it("states the kind and attribute an unscoped pool allocates to", async () => {
    // WHEN
    const component = await renderHeader(schemaPool);

    // THEN
    await expect.element(component.getByText("Allocates to")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "InfraInterface", exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "speed", exact: true }))
      .toBeVisible();
    await expect.element(component.getByText("with no scope")).toBeVisible();
  });

  it("lists the scope fields of a scoped pool by their schema labels", async () => {
    // WHEN
    const component = await renderHeader(userPool);

    // THEN
    await expect.element(component.getByText("scoped by")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Site", exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Role", exact: true }))
      .toBeVisible();
  });

  it("opens the schema of the kind in a modal", async () => {
    // GIVEN
    const component = await renderHeader(schemaPool);

    // WHEN
    await component.getByRole("button", { name: "InfraInterface", exact: true }).click();

    // THEN
    await expect.element(component.getByRole("dialog", { name: "Schema viewer" })).toBeVisible();
  });

  it("opens the schema of a scope field in a modal", async () => {
    // GIVEN
    const component = await renderHeader(userPool);

    // WHEN
    await component.getByRole("button", { name: "Site", exact: true }).click();

    // THEN
    await expect.element(component.getByRole("dialog", { name: "Schema viewer" })).toBeVisible();
  });

  it("shows a scope field missing from the schema by its stored name, without a modal", async () => {
    // WHEN
    const component = await renderHeader({
      ...userPool,
      allocation_scope: { value: ["site", "vrf"] },
    });

    // THEN
    await expect.element(component.getByText("vrf", { exact: true })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "vrf" })).not.toBeInTheDocument();
  });

  it("shows a kind missing from the schema without a modal", async () => {
    // WHEN
    const component = await renderHeader({ ...userPool, node: { value: "InfraRemoved" } });

    // THEN
    await expect.element(component.getByText("InfraRemoved", { exact: true })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "InfraRemoved" }))
      .not.toBeInTheDocument();
  });

  it("shows the description when the pool has one", async () => {
    // WHEN
    const component = await renderHeader(userPool);

    // THEN
    await expect.element(component.getByText("Speeds handed out to new interfaces")).toBeVisible();
  });

  it("shows the full id with a copy button", async () => {
    // WHEN
    const component = await renderHeader(userPool);

    // THEN
    await expect.element(component.getByText(userPool.id, { exact: true })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Copy ID" })).toBeVisible();
  });

  it("refreshes the number pool queries when the refresh button is pressed", async () => {
    // GIVEN
    const invalidateQueriesSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    const component = await renderHeader(userPool);

    // WHEN
    await component.getByRole("button", { name: "Refresh data" }).click();

    // THEN
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ["resource-manager"] });
    invalidateQueriesSpy.mockRestore();
  });

  it("offers the metadata, refresh and actions controls", async () => {
    // WHEN
    const component = await renderHeader(userPool);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "View node metadata" }))
      .toBeVisible();
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Actions" })).toBeVisible();
  });
});

describe("NumberPoolHeaderSkeleton", () => {
  it("shows a loading placeholder instead of the heading", async () => {
    // WHEN
    const component = await render(<NumberPoolHeaderSkeleton />);

    // THEN
    await expect
      .element(component.getByRole("status", { name: "Loading number pool" }))
      .toBeVisible();
    await expect.element(component.getByRole("heading")).not.toBeInTheDocument();
  });
});
