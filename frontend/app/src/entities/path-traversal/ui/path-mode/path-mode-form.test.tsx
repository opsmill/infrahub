import { describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { PathModeSidebar } from "./path-mode-sidebar";

describe("PathModeForm validation", () => {
  test("shows required errors when submitting with empty source and destination", async () => {
    const component = await render(<PathModeSidebar />);

    await component.getByRole("button", { name: /find paths/i }).click();

    await expect.element(component.getByText("Source is required")).toBeVisible();
    await expect.element(component.getByText("Destination is required")).toBeVisible();
  });
});
