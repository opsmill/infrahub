import { afterEach, describe, expect, test } from "vitest";

import { MarkdownRender } from "@/shared/components/editor/markdown/markdown-render";

import { render } from "../../../../../tests/components/render";

const DIAGRAM = "```mermaid\ngraph TD\n  A[Spine] --> B[Leaf]\n```";

// The assertions read the colours the browser actually paints on a node, because the palette
// reaches the SVG only through inherited CSS custom properties.
const nodeShape = () => document.querySelector<SVGGraphicsElement>("svg.pele .pele-node rect");

const luminance = (color: string): number => {
  const [r = 0, g = 0, b = 0] = (color.match(/[\d.]+/g) ?? []).map(Number);
  const f = (c: number) => {
    const s = c / 255;
    return s <= 0.039_28 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};

const shapeLuminance = () => {
  const shape = nodeShape();
  if (!shape) return null;
  return luminance(getComputedStyle(shape).fill);
};

const setDarkTheme = (dark: boolean) => document.documentElement.classList.toggle("dark", dark);

describe("Mermaid diagram theming", () => {
  afterEach(() => {
    setDarkTheme(false);
  });

  test("renders a light diagram in the light theme", async () => {
    // WHEN
    await render(<MarkdownRender markdownText={DIAGRAM} />);

    // THEN
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    expect(shapeLuminance()).toBeGreaterThan(0.5);
  });

  test("renders a dark diagram in the dark theme", async () => {
    // GIVEN
    setDarkTheme(true);

    // WHEN
    await render(<MarkdownRender markdownText={DIAGRAM} />);

    // THEN
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    expect(shapeLuminance()).toBeLessThan(0.5);
  });

  test("recolours the mounted diagram in place when the theme changes", async () => {
    // GIVEN
    await render(<MarkdownRender markdownText={DIAGRAM} />);
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    const shape = nodeShape();
    expect(shapeLuminance()).toBeGreaterThan(0.5);

    // WHEN
    setDarkTheme(true);

    // THEN
    expect(nodeShape()).toBe(shape);
    expect(shapeLuminance()).toBeLessThan(0.5);
  });
});
