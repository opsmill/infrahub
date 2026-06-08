import { describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import { GraphControls } from "./graph-controls";

vi.mock("@xyflow/react", () => ({
  useReactFlow: () => ({ zoomIn: vi.fn(), zoomOut: vi.fn(), fitView: vi.fn() }),
}));

describe("GraphControls", () => {
  test("renders the zoom/fit/layout controls by accessible name", async () => {
    // GIVEN / WHEN
    const component = await render(
      <GraphControls edgeStyle="bezier" onEdgeStyleChange={vi.fn()} onLayout={vi.fn()} />,
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Zoom out" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Fit to screen" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Auto-layout horizontal" }))
      .toBeVisible();
  });

  test("toggles the edge style", async () => {
    // GIVEN
    const onEdgeStyleChange = vi.fn();
    const component = await render(
      <GraphControls edgeStyle="bezier" onEdgeStyleChange={onEdgeStyleChange} onLayout={vi.fn()} />,
    );

    // WHEN
    await component.getByRole("button", { name: "Toggle edge style" }).click();

    // THEN it flips bezier -> smoothstep
    expect(onEdgeStyleChange).toHaveBeenCalledExactlyOnceWith("smoothstep");
  });

  test("triggers auto-layout", async () => {
    // GIVEN
    const onLayout = vi.fn();
    const component = await render(
      <GraphControls edgeStyle="bezier" onEdgeStyleChange={vi.fn()} onLayout={onLayout} />,
    );

    // WHEN
    await component.getByRole("button", { name: "Auto-layout vertical" }).click();

    // THEN
    expect(onLayout).toHaveBeenCalledExactlyOnceWith("TB");
  });
});
