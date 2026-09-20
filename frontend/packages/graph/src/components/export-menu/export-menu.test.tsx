import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { render } from "vitest-browser-react";

import { type ExportFormat, ExportMenu } from "./export-menu";

const onExportMock = () => vi.fn<(format: ExportFormat) => void>();

describe("ExportMenu", () => {
  test("toggles the menu and exports the chosen format", async () => {
    // GIVEN
    const onExport = onExportMock();
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

  test("exposes expanded state and moves focus into the menu on open", async () => {
    // GIVEN
    const component = await render(<ExportMenu onExport={onExportMock()} />);
    const trigger = component.getByRole("button", { name: "Export diagram" });

    // THEN the collapsed state is exposed
    await expect.element(trigger).toHaveAttribute("aria-expanded", "false");

    // WHEN the menu is opened
    await trigger.click();

    // THEN the expanded state is exposed and focus lands on the first option
    await expect.element(trigger).toHaveAttribute("aria-expanded", "true");
    await expect.element(component.getByRole("button", { name: "PNG" })).toHaveFocus();
  });

  test("returns focus to the trigger when the menu is dismissed with Escape", async () => {
    // GIVEN an open menu
    const component = await render(<ExportMenu onExport={onExportMock()} />);
    const trigger = component.getByRole("button", { name: "Export diagram" });
    await trigger.click();
    await expect.element(component.getByRole("button", { name: "PNG" })).toBeVisible();

    // WHEN pressing Escape
    await userEvent.keyboard("{Escape}");

    // THEN focus moves back to the trigger
    await expect.element(trigger).toHaveFocus();
  });

  test("closes on Escape without exporting", async () => {
    // GIVEN an open menu
    const onExport = onExportMock();
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
