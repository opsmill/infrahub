import { beforeEach, describe, expect, it } from "vitest";
import { page } from "vitest/browser";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../../tests/components/utils";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../../../tests/fake/schema";
import { ObjectDataRow } from "./object-data-row";

describe("ObjectDataRow", () => {
  const longLabel = "Maximum transmission unit override for the management interface";

  beforeEach(() => {
    store.set(nodeSchemasAtom, [generateNodeSchema({ kind: "TestDevice" })]);
  });

  it("shows the full label in a tooltip when the label is cut", async () => {
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
