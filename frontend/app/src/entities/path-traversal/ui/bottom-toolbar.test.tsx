import type React from "react";
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
  test("renders zoom controls by accessible name", async () => {
    const { component } = await setup();
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Zoom out" })).toBeVisible();
  });

  test("edge-style button shows 'Smooth' text when edgeStyle is bezier", async () => {
    const { component } = await setup({ edgeStyle: "bezier" });
    await expect.element(component.getByText("Smooth")).toBeVisible();
  });

  test("edge-style button shows 'Step' text when edgeStyle is smoothstep", async () => {
    const { component } = await setup({ edgeStyle: "smoothstep" });
    await expect.element(component.getByText("Step")).toBeVisible();
  });

  test("onEdgeStyleChange is called with 'smoothstep' when edgeStyle is bezier", async () => {
    const { props, component } = await setup({ edgeStyle: "bezier" });

    await component.getByRole("button", { name: "Toggle edge style" }).click();

    expect(props.onEdgeStyleChange).toHaveBeenCalledWith("smoothstep");
  });

  test("onEdgeStyleChange is called with 'bezier' when edgeStyle is smoothstep", async () => {
    const { props, component } = await setup({ edgeStyle: "smoothstep" });

    await component.getByRole("button", { name: "Toggle edge style" }).click();

    expect(props.onEdgeStyleChange).toHaveBeenCalledWith("bezier");
  });

  test("renders PNG and SVG export menu items when export menu is opened", async () => {
    const { component } = await setup();

    await component.getByRole("button", { name: "Export diagram" }).click();

    await expect.element(component.getByRole("button", { name: /PNG/i })).toBeVisible();
    await expect.element(component.getByRole("button", { name: /SVG/i })).toBeVisible();
  });

  test("onExport is called with 'png' when PNG is clicked", async () => {
    const { props, component } = await setup();

    await component.getByRole("button", { name: "Export diagram" }).click();
    (component.getByRole("button", { name: /PNG/i }).element() as HTMLElement).click();

    expect(props.onExport).toHaveBeenCalledWith("png");
  });

  test("onExport is called with 'svg' when SVG is clicked", async () => {
    const { props, component } = await setup();

    await component.getByRole("button", { name: "Export diagram" }).click();
    (component.getByRole("button", { name: /SVG/i }).element() as HTMLElement).click();

    expect(props.onExport).toHaveBeenCalledWith("svg");
  });

  test("onParametersClick fires when parameters button is clicked", async () => {
    const { props, component } = await setup({ isParametersOpen: false });

    await component.getByRole("button", { name: "Show parameters" }).click();

    expect(props.onParametersClick).toHaveBeenCalled();
  });

  test("isParametersOpen=true shows 'Hide parameters' button", async () => {
    const { component } = await setup({ isParametersOpen: true });
    await expect.element(component.getByRole("button", { name: "Hide parameters" })).toBeVisible();
  });

  test("onLayout fires with 'LR' when horizontal layout button is clicked", async () => {
    const { props, component } = await setup();

    await component.getByRole("button", { name: "Auto-layout horizontal" }).click();

    expect(props.onLayout).toHaveBeenCalledWith("LR");
  });

  test("onLayout fires with 'TB' when vertical layout button is clicked", async () => {
    const { props, component } = await setup();

    await component.getByRole("button", { name: "Auto-layout vertical" }).click();

    expect(props.onLayout).toHaveBeenCalledWith("TB");
  });

  test("reload button is absent when onReload is undefined, present and callable when provided", async () => {
    const { component: withoutReload } = await setup({ onReload: undefined });
    expect(withoutReload.getByRole("button", { name: "Reload" }).elements()).toHaveLength(0);

    const onReload = vi.fn();
    const { component: withReload } = await setup({ onReload });
    await expect.element(withReload.getByRole("button", { name: "Reload" })).toBeVisible();
    await withReload.getByRole("button", { name: "Reload" }).click();
    expect(onReload).toHaveBeenCalled();
  });
});
