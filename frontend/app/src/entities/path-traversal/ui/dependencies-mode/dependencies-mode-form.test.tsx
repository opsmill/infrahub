import { describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { DependenciesModeSidebar } from "./dependencies-mode-sidebar";

describe("DependenciesModeForm validation", () => {
  test("shows required errors when submitting with empty fields", async () => {
    const component = await render(<DependenciesModeSidebar />);

    await component.getByRole("button", { name: /find dependencies/i }).click();

    await expect.element(component.getByText("Source is required")).toBeVisible();
    await expect.element(component.getByText("Select at least one target kind")).toBeVisible();
  });

  test("exposes the shortest paths only option, checked by default", async () => {
    const component = await render(<DependenciesModeSidebar />);

    await component.getByRole("button", { name: /search options/i }).click();

    const checkbox = component.getByRole("checkbox", { name: /shortest paths only/i });
    await expect.element(checkbox).toBeVisible();
    await expect.element(checkbox).toBeChecked();
  });
});
