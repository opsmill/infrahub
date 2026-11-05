import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { Combobox } from "./combobox";

const RED_ITEM = { value: "RED", label: "Red", icon: <span data-testid="red-swatch" /> };

describe("Combobox", () => {
  test("renders an item's icon before its label while keeping the label as the option name", async () => {
    // GIVEN
    const component = await render(
      <Combobox value={null} onChange={() => {}} label="Instance color" items={[RED_ITEM]} />
    );

    // WHEN
    await component.getByRole("button", { name: "Instance color" }).click();

    // THEN
    const option = component.getByRole("option", { name: "Red", exact: true });
    await expect.element(option).toBeVisible();
    await expect.element(option.getByTestId("red-swatch")).toBeInTheDocument();
  });

  test("shows the selected item's icon next to its label on the closed trigger", async () => {
    // GIVEN
    const value = "RED";

    // WHEN
    const component = await render(
      <Combobox value={value} onChange={() => {}} label="Instance color" items={[RED_ITEM]} />
    );

    // THEN
    const trigger = component.getByRole("button", { name: "Instance color" });
    await expect.element(trigger).toHaveTextContent("Red");
    await expect.element(trigger.getByTestId("red-swatch")).toBeInTheDocument();
  });

  test("shows the placeholder without any icon when nothing is selected", async () => {
    // GIVEN
    const value = null;

    // WHEN
    const component = await render(
      <Combobox
        value={value}
        onChange={() => {}}
        label="Instance color"
        placeholder="No color"
        items={[RED_ITEM]}
      />
    );

    // THEN
    const trigger = component.getByRole("button", { name: "Instance color" });
    await expect.element(trigger).toHaveTextContent("No color");
    expect(trigger.getByTestId("red-swatch").query()).toBeNull();
  });
});
