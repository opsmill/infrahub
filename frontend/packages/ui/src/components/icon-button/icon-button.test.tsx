import { describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import { IconButton } from "./icon-button";

describe("IconButton", () => {
  test("exposes its accessible name from aria-label", async () => {
    // GIVEN an icon-only button with an aria-label
    const component = await render(
      <IconButton aria-label="Zoom in">
        <svg aria-hidden="true" />
      </IconButton>,
    );

    // THEN it is reachable by role + accessible name
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
  });

  test("fires onPress when activated", async () => {
    // GIVEN
    const onPress = vi.fn();
    const component = await render(
      <IconButton aria-label="Reload" onPress={onPress}>
        <svg aria-hidden="true" />
      </IconButton>,
    );

    // WHEN pressed
    await component.getByRole("button", { name: "Reload" }).click();

    // THEN
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  test("does not fire onPress when disabled", async () => {
    // GIVEN
    const onPress = vi.fn();
    const component = await render(
      <IconButton aria-label="Reload" onPress={onPress} isDisabled>
        <svg aria-hidden="true" />
      </IconButton>,
    );

    // WHEN attempting to press (force past pointer-events:none on disabled buttons)
    await component.getByRole("button", { name: "Reload" }).click({ force: true });

    // THEN
    expect(onPress).not.toHaveBeenCalled();
  });
});
