import { Button } from "@infrahub/ui";
import { describe, expect, test } from "vitest";
import { render } from "vitest-browser-react";

import { Toolbar } from "./toolbar";

describe("Toolbar", () => {
  test("renders with the toolbar role and accessible name", async () => {
    // GIVEN
    const component = await render(
      <Toolbar aria-label="Graph controls">
        <Button variant="ghost" size="sm" shape="square" aria-label="Zoom in">
          <svg aria-hidden="true" />
        </Button>
      </Toolbar>,
    );

    // THEN
    await expect.element(component.getByRole("toolbar", { name: "Graph controls" })).toBeVisible();
  });

  test("renders child controls reachable by name", async () => {
    // GIVEN
    const component = await render(
      <Toolbar aria-label="Graph controls">
        <Button variant="ghost" size="sm" shape="square" aria-label="Zoom in">
          <svg aria-hidden="true" />
        </Button>
        <Toolbar.Divider />
        <Button variant="ghost" size="sm" shape="square" aria-label="Zoom out">
          <svg aria-hidden="true" />
        </Button>
      </Toolbar>,
    );

    // THEN both buttons + the separator exist
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Zoom out" })).toBeVisible();
    await expect.element(component.getByRole("separator")).toBeVisible();
  });
});
