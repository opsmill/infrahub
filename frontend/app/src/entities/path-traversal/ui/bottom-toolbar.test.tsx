import React from "react";
import { describe, expect, test, vi } from "vitest";
import { render } from "../../../../tests/components/render";

import { BottomToolbar } from "./bottom-toolbar";

vi.mock("@xyflow/react", () => ({
  Panel: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  useReactFlow: () => ({ zoomIn: vi.fn(), zoomOut: vi.fn(), fitView: vi.fn() }),
}));

type Props = React.ComponentProps<typeof BottomToolbar>;

async function setup(overrides: Partial<Props> = {}) {
  const props: Props = {
    onParametersClick: vi.fn(),
    isParametersOpen: false,
    edgeStyle: "bezier",
    onEdgeStyleChange: vi.fn(),
    onLayout: vi.fn(),
    onExport: vi.fn(),
    onReload: vi.fn(),
    isReloading: false,
    ...overrides,
  };
  const component = await render(<BottomToolbar {...props} />);
  return { props, component };
}

describe("BottomToolbar", () => {
  test("renders without crashing", async () => {
    const { component } = await setup();
    await expect.element(component.getByRole("button", { name: /Smooth/i })).toBeVisible();
  });

  test("edge-style button shows 'Smooth' text when edgeStyle is bezier", async () => {
    const { component } = await setup({ edgeStyle: "bezier" });
    await expect.element(component.getByRole("button", { name: /Smooth/i })).toBeVisible();
  });

  test("edge-style button shows 'Step' text when edgeStyle is smoothstep", async () => {
    const { component } = await setup({ edgeStyle: "smoothstep" });
    await expect.element(component.getByRole("button", { name: /Step/i })).toBeVisible();
  });

  test("onEdgeStyleChange is called with 'smoothstep' when edgeStyle is bezier", async () => {
    const { props, component } = await setup({ edgeStyle: "bezier" });

    await component.getByRole("button", { name: /Smooth/i }).click();

    expect(props.onEdgeStyleChange).toHaveBeenCalledWith("smoothstep");
  });

  test("onEdgeStyleChange is called with 'bezier' when edgeStyle is smoothstep", async () => {
    const { props, component } = await setup({ edgeStyle: "smoothstep" });

    await component.getByRole("button", { name: /Step/i }).click();

    expect(props.onEdgeStyleChange).toHaveBeenCalledWith("bezier");
  });

  test("renders PNG and SVG export menu items when export menu is opened", async () => {
    const { component } = await setup();

    // The export button is the last button in the toolbar (icon-only, no accessible name yet)
    const allButtons = component.getByRole("button");
    const count = allButtons.elements().length;
    await allButtons.nth(count - 1).click();

    await expect.element(component.getByRole("button", { name: /PNG/i })).toBeVisible();
    await expect.element(component.getByRole("button", { name: /SVG/i })).toBeVisible();
  });

  test("onExport is called with 'png' when PNG is clicked", async () => {
    const { props, component } = await setup();

    const allButtons = component.getByRole("button");
    const count = allButtons.elements().length;
    await allButtons.nth(count - 1).click();

    // Menu popup may be above the test viewport; dispatch click directly
    const pngBtn = component.getByRole("button", { name: /PNG/i }).elements()[0];
    pngBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    expect(props.onExport).toHaveBeenCalledWith("png");
  });

  test("onExport is called with 'svg' when SVG is clicked", async () => {
    const { props, component } = await setup();

    const allButtons = component.getByRole("button");
    const count = allButtons.elements().length;
    await allButtons.nth(count - 1).click();

    // Menu popup may be above the test viewport; dispatch click directly
    const svgBtn = component.getByRole("button", { name: /SVG/i }).elements()[0];
    svgBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    expect(props.onExport).toHaveBeenCalledWith("svg");
  });

  test("onParametersClick fires when parameters button is clicked", async () => {
    // With onReload provided: zoom-out(0) fit(1) zoom-in(2) edge-style(3)
    // layout-lr(4) layout-tb(5) parameters(6) reload(7) export-trigger(8)
    const { props, component } = await setup({ isParametersOpen: false });

    const allButtons = component.getByRole("button");
    const count = allButtons.elements().length;
    // parameters is 3rd from end: [count-3] (before reload and export-trigger)
    await allButtons.nth(count - 3).click();

    expect(props.onParametersClick).toHaveBeenCalled();
  });

  test("onLayout fires with 'LR' when horizontal layout button is clicked", async () => {
    const { props, component } = await setup();
    // zoom-out(0) fit(1) zoom-in(2) edge-style(3) layout-lr(4) ...
    const allButtons = component.getByRole("button");
    await allButtons.nth(4).click();
    expect(props.onLayout).toHaveBeenCalledWith("LR");
  });

  test("onLayout fires with 'TB' when vertical layout button is clicked", async () => {
    const { props, component } = await setup();
    const allButtons = component.getByRole("button");
    await allButtons.nth(5).click();
    expect(props.onLayout).toHaveBeenCalledWith("TB");
  });
});
