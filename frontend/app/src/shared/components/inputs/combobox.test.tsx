import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { Combobox } from "./combobox";

describe("Combobox", () => {
  test("renders an item's icon before its label while keeping the label as the option name", async () => {
    // GIVEN
    const component = await render(
      <Combobox
        value={null}
        onChange={() => {}}
        label="Instance color"
        items={[{ value: "RED", label: "Red", icon: <span data-testid="red-swatch" /> }]}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Instance color" }).click();

    // THEN
    const option = component.getByRole("option", { name: "Red", exact: true });
    await expect.element(option).toBeVisible();
    await expect.element(option.getByTestId("red-swatch")).toBeInTheDocument();
  });
});
