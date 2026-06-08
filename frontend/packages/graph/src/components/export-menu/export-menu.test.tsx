import { describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";
import { userEvent } from "vitest/browser";

import { ExportMenu } from "./export-menu";

describe("ExportMenu", () => {
  test("toggles the menu and exports the chosen format", async () => {
    // GIVEN
    const onExport = vi.fn();
    const component = await render(<ExportMenu onExport={onExport} />);

    // WHEN the menu is opened
    await component.getByRole("button", { name: "Export diagram" }).click();

    // THEN the format options are shown
    await expect.element(component.getByRole("button", { name: "PNG" })).toBeVisible();

    // WHEN a format is chosen (native click — the popover renders above the trigger,
    // outside the headless viewport)
    (component.getByRole("button", { name: "PNG" }).element() as HTMLElement).click();

    // THEN onExport fires with that format
    expect(onExport).toHaveBeenCalledExactlyOnceWith("png");
  });

  test("closes on Escape without exporting", async () => {
    // GIVEN an open menu
    const onExport = vi.fn();
    const component = await render(<ExportMenu onExport={onExport} />);
    await component.getByRole("button", { name: "Export diagram" }).click();
    await expect.element(component.getByRole("button", { name: "SVG" })).toBeVisible();

    // WHEN pressing Escape
    await userEvent.keyboard("{Escape}");

    // THEN the menu closes (its options leave the DOM) and nothing is exported
    await expect.element(component.getByRole("button", { name: "SVG" })).not.toBeInTheDocument();
    await expect.element(component.getByRole("button", { name: "PNG" })).not.toBeInTheDocument();
    expect(onExport).not.toHaveBeenCalled();
  });
});
