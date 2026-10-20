import { describe, expect, it } from "vitest";

import { render } from "../../../../../tests/components/render";
import { GitStatePill } from "./git-state-pill";

describe("GitStatePill", () => {
  it("shows the status label, not its value, when the status has no colour", async () => {
    // WHEN
    const component = await render(
      <GitStatePill
        syncStatus={{
          value: "error-import",
          label: "Import failed",
          color: null,
          description: null,
        }}
      />
    );

    // THEN
    await expect.element(component.getByText("Import failed")).toBeVisible();
    expect(component.container.textContent).not.toContain("error-import");
  });

  it("shows the status value when the status has no label", async () => {
    // WHEN
    const component = await render(
      <GitStatePill
        syncStatus={{ value: "error-import", label: null, color: null, description: null }}
      />
    );

    // THEN
    await expect.element(component.getByText("error-import")).toBeVisible();
  });

  it("paints the status colour behind the label", async () => {
    // WHEN
    const component = await render(
      <GitStatePill
        syncStatus={{
          value: "in-sync",
          label: "In sync",
          color: "#16a34a",
          description: null,
        }}
      />
    );

    // THEN
    await expect
      .element(component.getByText("In sync"))
      .toHaveStyle({ backgroundColor: "rgb(22, 163, 74)" });
  });

  it("does not paint the colour when the status has no label", async () => {
    // WHEN
    const component = await render(
      <GitStatePill
        syncStatus={{ value: "in-sync", label: null, color: "#16a34a", description: null }}
      />
    );

    // THEN
    await expect
      .element(component.getByText("in-sync"))
      .not.toHaveStyle({ backgroundColor: "rgb(22, 163, 74)" });
  });
});
