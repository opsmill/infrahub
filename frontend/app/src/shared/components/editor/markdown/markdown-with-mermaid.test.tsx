import { describe, expect, test } from "vitest";

import MarkdownWithMermaid from "@/shared/components/editor/markdown/markdown-with-mermaid";

import type { ResolvedTheme } from "@/entities/config/domain/model/theme";
import { ThemeContext } from "@/entities/config/ui/theme-provider";

import { render } from "../../../../../tests/components/render";

const DIAGRAM = "```mermaid\ngraph TD\n  A[Spine] --> B[Leaf]\n```";

// The rendered diagram is a real mermaid SVG, so the assertions read the colors it actually baked
// in rather than trusting configuration to have reached it — that trust is exactly what broke the
// first implementation, when the renderer silently discarded the config it was handed.
const nodeShape = () =>
  document.querySelector<SVGGraphicsElement>("svg .node rect, svg .node path, svg .node polygon");

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

const inTheme = (theme: ResolvedTheme, markdownText = DIAGRAM) => (
  <ThemeContext value={{ theme, resolvedTheme: theme, setTheme: () => {} }}>
    <MarkdownWithMermaid markdownText={markdownText} fallback={null} />
  </ThemeContext>
);

describe("MarkdownWithMermaid", () => {
  test("renders a light diagram in the light theme", async () => {
    // WHEN
    await render(inTheme("light"));

    // THEN
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    expect(shapeLuminance()).toBeGreaterThan(0.5);
  });

  test("renders a dark diagram in the dark theme", async () => {
    // WHEN
    await render(inTheme("dark"));

    // THEN
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    expect(shapeLuminance()).toBeLessThan(0.5);
  });

  test("re-renders the diagram when the theme changes while mounted", async () => {
    // GIVEN
    const component = await render(inTheme("light"));
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    const light = shapeLuminance();

    // WHEN
    await component.rerender(inTheme("dark"));

    // THEN
    // The flip re-runs the pipeline; poll until the freshly baked SVG replaces the light one.
    await expect
      .poll(
        () => {
          const value = shapeLuminance();
          return value !== null && value < 0.5;
        },
        { timeout: 15_000 }
      )
      .toBe(true);
    expect(light).toBeGreaterThan(0.5);
  });

  test("a diagram's own init directive beats the application theme", async () => {
    // GIVEN
    const source = '```mermaid\n%%{init: {"theme":"default"}}%%\ngraph TD\n  A --> B\n```';

    // WHEN
    await render(inTheme("dark", source));

    // THEN
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    expect(shapeLuminance()).toBeGreaterThan(0.5);
  });
});
