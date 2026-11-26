import { describe, expect, it, vi } from "vitest";
import { userEvent } from "vitest/browser";

import type { NodeAttributeWithMetadata } from "@/entities/nodes/object/domain/model/node";

import { render } from "../../../../../../../tests/components/render";
import { generatePermission } from "../../../../../../../tests/fake/permission";
import { generateAttributeSchema } from "../../../../../../../tests/fake/schema";
import { ObjectAttributeRow } from "./object-attribute-row";

describe("ObjectAttributeRow", () => {
  const attributeSchema = generateAttributeSchema({ name: "name", label: "Name" });
  const permission = generatePermission();
  const attributeData: NodeAttributeWithMetadata = {
    value: "Device name",
    updated_at: "2024-01-01T00:00:00Z",
    is_protected: true,
    is_default: false,
    is_from_profile: false,
    is_visible: true,
    source: null,
    owner: null,
  };

  it("shows the metadata icon while the pointer is over the row", async () => {
    // GIVEN
    const component = await render(
      <ObjectAttributeRow
        attributeSchema={attributeSchema}
        attributeData={attributeData}
        permission={permission}
        objectKind="TestDevice"
      />
    );
    const icon = component
      .getByRole("button", { name: "View metadata" })
      .element()
      .querySelector("iconify-icon");
    if (!icon) throw new Error("Missing metadata icon");
    await userEvent.hover(document.body, { position: { x: 1200, y: 700 } });
    await expect.poll(() => getComputedStyle(icon).opacity).toBe("0");

    // WHEN
    await component.getByText("Name", { exact: true }).hover();

    // THEN
    await expect.poll(() => getComputedStyle(icon).opacity).toBe("1");
  });

  it("calls onClickMetadata from the edit action of the metadata popover", async () => {
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
    await component.getByRole("button", { name: "View metadata" }).click();

    // WHEN
    await component.getByRole("button", { name: "Edit metadata" }).click();

    // THEN
    expect(onClickMetadata).toHaveBeenCalledWith(attributeSchema);
  });

  it.each([true, false])(
    "shows the lock icon before the metadata icon only when protected (%s)",
    async (isProtected) => {
      // WHEN
      const component = await render(
        <ObjectAttributeRow
          attributeSchema={attributeSchema}
          attributeData={{ ...attributeData, is_protected: isProtected }}
          permission={permission}
          objectKind="TestDevice"
        />
      );

      // THEN
      const lock = component.container.querySelector("svg.lucide-lock");
      if (isProtected) {
        expect(lock?.nextElementSibling).toBe(
          component.getByRole("button", { name: "View metadata" }).element()
        );
      } else {
        expect(lock).toBeNull();
      }
    }
  );
});
