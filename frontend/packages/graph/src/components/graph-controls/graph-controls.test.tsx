import { beforeEach, describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import { type EdgeStyle, GraphControls, type LayoutDirection } from "./graph-controls";

// Hoisted so the same mock fns are asserted against across renders (a fresh vi.fn() per
// useReactFlow() call would be unobservable from the test).
const reactFlow = vi.hoisted(() => ({
  zoomIn: vi.fn<() => void>(),
  zoomOut: vi.fn<() => void>(),
  fitView: vi.fn<(options?: { padding: number }) => void>(),
}));

vi.mock("@xyflow/react", () => ({
  useReactFlow: () => reactFlow,
}));

beforeEach(() => {
  vi.clearAllMocks();
});

const onEdgeStyleChangeMock = () => vi.fn<(style: EdgeStyle) => void>();
const onLayoutMock = () => vi.fn<(direction: LayoutDirection) => void>();

describe("GraphControls", () => {
  test("renders the zoom/fit/layout controls by accessible name", async () => {
    // GIVEN / WHEN
    const component = await render(
      <GraphControls
        edgeStyle="bezier"
        onEdgeStyleChange={onEdgeStyleChangeMock()}
        onLayout={onLayoutMock()}
      />
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
    const onEdgeStyleChange = onEdgeStyleChangeMock();
    const component = await render(
      <GraphControls
        edgeStyle="bezier"
        onEdgeStyleChange={onEdgeStyleChange}
        onLayout={onLayoutMock()}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Toggle edge style" }).click();

    // THEN it flips bezier -> smoothstep
    expect(onEdgeStyleChange).toHaveBeenCalledExactlyOnceWith("smoothstep");
  });

  test("triggers auto-layout", async () => {
    // GIVEN
    const onLayout = onLayoutMock();
    const component = await render(
      <GraphControls
        edgeStyle="bezier"
        onEdgeStyleChange={onEdgeStyleChangeMock()}
        onLayout={onLayout}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Auto-layout vertical" }).click();

    // THEN
    expect(onLayout).toHaveBeenCalledExactlyOnceWith("TB");
  });

  test("zoom in / out and fit to screen call the ReactFlow controls", async () => {
    // GIVEN
    const component = await render(
      <GraphControls
        edgeStyle="bezier"
        onEdgeStyleChange={onEdgeStyleChangeMock()}
        onLayout={onLayoutMock()}
      />
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
