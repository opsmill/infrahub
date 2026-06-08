import { beforeEach, describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import { GraphControls } from "./graph-controls";

// Hoisted so the same mock fns are asserted against across renders (a fresh vi.fn() per
// useReactFlow() call would be unobservable from the test).
const reactFlow = vi.hoisted(() => ({
  zoomIn: vi.fn(),
  zoomOut: vi.fn(),
  fitView: vi.fn(),
}));

vi.mock("@xyflow/react", () => ({
  useReactFlow: () => reactFlow,
}));

beforeEach(() => {
  vi.clearAllMocks();
});

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

  test("zoom in / out and fit to screen call the ReactFlow controls", async () => {
    // GIVEN
    const component = await render(
      <GraphControls edgeStyle="bezier" onEdgeStyleChange={vi.fn()} onLayout={vi.fn()} />,
    );

    // WHEN / THEN
    await component.getByRole("button", { name: "Zoom in" }).click();
    expect(reactFlow.zoomIn).toHaveBeenCalledOnce();

    await component.getByRole("button", { name: "Zoom out" }).click();
    expect(reactFlow.zoomOut).toHaveBeenCalledOnce();

    await component.getByRole("button", { name: "Fit to screen" }).click();
    expect(reactFlow.fitView).toHaveBeenCalledExactlyOnceWith({ padding: 0.2 });
  });
});
