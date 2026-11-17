import type { CDPSession } from "@vitest/browser-playwright";
import { beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { cdp, userEvent } from "vitest/browser";

import { store } from "@/shared/stores";

import type { NodeRelationshipMetadata } from "@/entities/nodes/object/domain/model/node";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../tests/components/render";
import { generatePermission } from "../../../../../../../tests/fake/permission";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../../tests/fake/schema";
import { ObjectAttributeRow } from "./object-attribute-row";
import { ObjectFieldMetadata } from "./object-field-metadata";
import { ObjectRelationshipRow } from "./object-relationship-row";

const metadata: NodeRelationshipMetadata = {
  updated_at: "2024-01-01T00:00:00Z",
  is_protected: true,
  source: { id: "source-1", __typename: "TestSource", display_label: "Source object" },
  owner: { id: "owner-1", __typename: "TestOwner", display_label: "Owner object" },
};
const permission = generatePermission();
const attributeSchema = generateAttributeSchema({ name: "name", label: "Name" });
const attributeData = {
  ...metadata,
  value: "Device name",
  updated_at: "2024-01-01T00:00:00Z",
  is_protected: true,
  is_default: false,
  is_from_profile: false,
  is_visible: true,
};
const relationshipSchema = generateRelationshipSchema({ name: "tags", label: "Tags" });
const edges = ["First tag", "Second tag"].map((label, index) => ({
  node: { id: `tag-${index}`, __typename: "TestTag", display_label: label },
  properties: metadata,
}));

describe("ObjectFieldMetadata", () => {
  beforeEach(() => {
    store.set(
      nodeSchemasAtom,
      ["TestSource", "TestOwner", "TestTag"].map((kind) =>
        generateNodeSchema({ kind, display_labels: ["name__value"] })
      )
    );
  });

  it.each([
    {
      name: "attribute",
      label: "Name",
      row: (
        <ObjectAttributeRow
          attributeSchema={attributeSchema}
          attributeData={attributeData}
          permission={permission}
          objectKind="TestDevice"
        />
      ),
    },
    {
      name: "single relationship",
      label: "Tags",
      row: (
        <ObjectRelationshipRow
          relationshipSchema={{ ...relationshipSchema, cardinality: "one" }}
          relationshipData={{ node: null, properties: metadata }}
          permission={permission}
          objectKind="TestDevice"
        />
      ),
    },
  ])("reveals $name metadata when hovering its field label", async ({ row, label }) => {
    // GIVEN
    const component = await render(row);
    const trigger = component.getByTestId("view-metadata-button");
    await userEvent.hover(document.body, { position: { x: 1200, y: 700 } });
    await expect.element(trigger).toHaveStyle({ opacity: "0" });

    // WHEN
    await component.getByText(label, { exact: true }).hover();

    // THEN
    await expect.element(trigger).toHaveStyle({ opacity: "1" });
  });

  it("reveals only the hovered relationship item's metadata across the row width", async () => {
    // GIVEN
    const component = await render(
      <ObjectRelationshipRow
        relationshipSchema={{ ...relationshipSchema, cardinality: "many" }}
        relationshipData={{ edges }}
        permission={permission}
        objectKind="TestDevice"
      />
    );
    const triggers = component.getByTestId("view-metadata-button");
    const row = component.getByRole("link", { name: "First tag" }).element().parentElement;
    if (!row) throw new Error("Missing relationship item row");

    // WHEN
    await userEvent.hover(row, { position: { x: row.clientWidth - 5, y: 5 } });

    // THEN
    await expect.element(triggers.nth(0)).toHaveStyle({ opacity: "1" });
    await expect.element(triggers.nth(1)).toHaveStyle({ opacity: "0" });
  });

  it("reveals the metadata button when reached with the keyboard", async () => {
    // GIVEN
    const component = await render(
      <>
        <button type="button">Start</button>
        <ObjectFieldMetadata metadata={metadata} />
      </>
    );
    await component.getByRole("button", { name: "Start" }).click();

    // WHEN
    await userEvent.tab();

    // THEN
    const trigger = component.getByTestId("view-metadata-button");
    await expect.element(trigger).toHaveFocus();
    await expect.element(trigger).toHaveStyle({ opacity: "1" });
  });

  it.each([
    "row",
    "edge",
  ] as const)("keeps %s metadata visible on touch-only devices", async (hoverScope) => {
    // GIVEN
    const session: CDPSession = cdp();
    onTestFinished(async () => {
      await session.send("Emulation.setTouchEmulationEnabled", { enabled: false });
    });
    await session.send("Emulation.setTouchEmulationEnabled", { enabled: true });
    expect(window.matchMedia("(hover: none)").matches).toBe(true);

    // WHEN
    const component = await render(
      <ObjectFieldMetadata metadata={metadata} hoverScope={hoverScope} />
    );

    // THEN
    await expect
      .element(component.getByTestId("view-metadata-button"))
      .toHaveStyle({ opacity: "1" });
  });

  it("preserves metadata content and the attribute edit action", async () => {
    // GIVEN
    const onClickMetadata = vi.fn();
    const component = await render(
      <ObjectAttributeRow
        attributeSchema={attributeSchema}
        attributeData={attributeData}
        permission={permission}
        objectKind="TestDevice"
        onClickMetadata={onClickMetadata}
      />
    );
    await component.getByTestId("view-metadata-button").click();
    await expect.element(component.getByRole("link", { name: "Source object" })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Owner object" })).toBeVisible();
    await expect.element(component.getByText("True", { exact: true })).toBeVisible();

    // WHEN
    await component.getByTestId("edit-metadata-button").click();

    // THEN
    expect(onClickMetadata).toHaveBeenCalledWith(attributeSchema);
  });

  it.each([
    true,
    false,
    null,
  ])("renders the lock before metadata only when protected (%s)", async (isProtected) => {
    // GIVEN
    const fieldMetadata = { ...metadata, is_protected: isProtected };

    // WHEN
    const component = await render(<ObjectFieldMetadata metadata={fieldMetadata} />);

    // THEN
    const lock = component.container.querySelector("svg.lucide-lock");
    if (isProtected) {
      expect(lock).not.toBeNull();
      expect(lock?.nextElementSibling).toBe(
        component.getByTestId("view-metadata-button").element()
      );
    } else {
      expect(lock).toBeNull();
    }
  });
});
