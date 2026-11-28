import { describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { PcPlaceholderButton } from "./pc-placeholder-button";

describe("PcPlaceholderButton", () => {
  test("disables both buttons and offers no picker", async () => {
    // GIVEN
    const placeholder = <PcPlaceholderButton />;

    // WHEN
    const component = await render(placeholder);

    // THEN
    await expect.element(component.getByRole("button", { name: "Please login" })).toBeDisabled();
    const chevron = component.getByRole("button").nth(1);
    await expect.element(chevron).toBeDisabled();
    await expect.element(chevron).not.toHaveAttribute("data-testid");
    await expect.element(chevron).not.toHaveAttribute("aria-label");
  });
});
