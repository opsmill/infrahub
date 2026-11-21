import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import { type PcActionComboboxItem, PcActionComboboxList } from "./pc-action-combobox-list";

const available = (action: string) => ({ action, available: true, unavailability_reason: null });

const mergeItem: PcActionComboboxItem<"merge"> = {
  value: "merge",
  name: "Merge",
  availability: available("merge"),
};

const actionItems: PcActionComboboxItem<"merge" | "close">[] = [
  mergeItem,
  { value: "close", name: "Close", availability: available("close") },
];

describe("PcActionComboboxList", () => {
  test.each([
    { name: "backend availability", items: actionItems },
    {
      name: "no availability",
      items: [
        { value: "merge", name: "Merge" },
        { value: "close", name: "Close" },
      ],
    },
  ])("selects an available item with $name", async ({ items }) => {
    // GIVEN
    const onSelect = vi.fn();
    const component = await render(
      <PcActionComboboxList items={items} value="merge" onSelect={onSelect} />
    );

    // WHEN
    await component.getByRole("option", { name: "Close" }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledExactlyOnceWith("close");
  });

  test("shows an unavailable item as text with its reason instead of an option", async () => {
    // GIVEN
    const items: PcActionComboboxItem<"merge" | "close">[] = [
      mergeItem,
      {
        value: "close",
        name: "Close",
        availability: {
          action: "close",
          available: false,
          unavailability_reason: "Only open proposed changes can close",
        },
      },
    ];
    const component = await render(
      <PcActionComboboxList items={items} value="merge" onSelect={vi.fn()} />
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("Close", { exact: true }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "Only open proposed changes can close" }))
      .toBeVisible();
    expect(component.getByRole("option", { name: "Close" }).query()).toBeNull();
    await initPointerTracking(component.locator);
  });

  test("marks the selected value with a check", async () => {
    // GIVEN
    const value = "close";

    // WHEN
    const component = await render(
      <PcActionComboboxList items={actionItems} value={value} onSelect={vi.fn()} />
    );

    // THEN
    const checkIcon = (name: string) =>
      component.getByRole("option", { name }).element().querySelector("iconify-icon");
    await expect.element(component.getByRole("option", { name: "Close" })).toBeVisible();
    expect(checkIcon("Close")).toHaveStyle({ opacity: "1" });
    expect(checkIcon("Merge")).toHaveStyle({ opacity: "0" });
  });
});
