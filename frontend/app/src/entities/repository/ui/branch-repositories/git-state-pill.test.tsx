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
});
