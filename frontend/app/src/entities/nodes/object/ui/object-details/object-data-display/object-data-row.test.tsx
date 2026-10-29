import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { page } from "vitest/browser";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../../tests/components/utils";
import {
  generateAttributeSchema,
  generateNodeSchema,
} from "../../../../../../../tests/fake/schema";
import { ObjectDataRow } from "./object-data-row";

describe("ObjectDataRow", () => {
  const longLabel = "Maximum transmission unit override for the management interface";
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeAll(() => store.set(nodeSchemasAtom, [generateNodeSchema({ kind: "TestDevice" })]));
  afterAll(() => store.set(nodeSchemasAtom, initialNodeSchemas));

  it("shows the full label in a tooltip when the label is truncated", async () => {
    // GIVEN
    const component = await render(
      <ObjectDataRow
        fieldSchema={generateAttributeSchema({ name: "mtu_override", label: longLabel })}
        objectKind="TestDevice"
        value="1500"
      />
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("button", { name: longLabel }).hover();

    // THEN
    await expect.element(page.getByRole("tooltip")).toHaveTextContent(longLabel);
    await initPointerTracking(component.locator);
  });

  it("closes the tooltip when the label is clicked to open the schema", async () => {
    // GIVEN
    const component = await render(
      <ObjectDataRow
        fieldSchema={generateAttributeSchema({ name: "mtu_override", label: longLabel })}
        objectKind="TestDevice"
        value="1500"
      />
    );
    await initPointerTracking(component.locator);
    const label = component.getByRole("button", { name: longLabel });
    await label.hover();
    await expect.element(page.getByRole("tooltip")).toBeVisible();

    // WHEN
    await label.click();

    // THEN
    await expect.element(page.getByRole("dialog")).toBeVisible();
    await expect.element(page.getByRole("tooltip")).not.toBeInTheDocument();
  });

  it("does not show a tooltip when the label fits", async () => {
    // GIVEN
    const component = await render(
      <ObjectDataRow
        fieldSchema={generateAttributeSchema({ name: "mtu", label: "MTU" })}
        objectKind="TestDevice"
        value="1500"
      />
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("button", { name: "MTU" }).hover();
    await new Promise((resolve) => setTimeout(resolve, 500));

    // THEN
    expect(page.getByRole("tooltip").query()).toBeNull();
  });
});
