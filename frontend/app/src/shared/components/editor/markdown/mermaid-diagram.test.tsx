import type * as Pele from "pele/lazy";
import { afterEach, describe, expect, test, vi } from "vitest";

import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";

import { render } from "../../../../../tests/components/render";

const { loadMock } = vi.hoisted(() => ({ loadMock: vi.fn() }));

// typeLoads keeps one load per diagram type for the whole file, so each test uses a different type.
vi.mock("pele/lazy", async (importOriginal) => {
  const actual = await importOriginal<typeof Pele>();
  loadMock.mockImplementation(actual.load);
  return { ...actual, load: loadMock };
});

const nodeShape = () => document.querySelector<SVGGraphicsElement>("svg.pele .pele-node rect");

const luminance = (color: string): number => {
  const [r = 0, g = 0, b = 0] = (color.match(/[\d.]+/g) ?? []).map(Number);
  const f = (c: number) => {
    const s = c / 255;
    return s <= 0.039_28 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};

// shapeLuminance reads the painted fill, because the palette reaches the svg only through inherited CSS variables.
const shapeLuminance = () => {
  const shape = nodeShape();
  if (!shape) return null;
  return luminance(getComputedStyle(shape).fill);
};

const setDarkTheme = (dark: boolean) => document.documentElement.classList.toggle("dark", dark);

describe("MermaidDiagram", () => {
  afterEach(() => {
    setDarkTheme(false);
  });

  // React logs a misuse of `use` only once per page, so this test must load the file's first diagram type.
  test("draws a diagram once its type's code has loaded, without a React error", async () => {
    // GIVEN
    const consoleError = vi.spyOn(console, "error");

    // WHEN
    const component = await render(<MermaidDiagram code={"gitGraph\n  commit"} />);

    // THEN
    await expect.poll(() => component.container.querySelector("svg.pele")).toBeTruthy();
    expect(consoleError).not.toHaveBeenCalled();
  });

  test("asks for a reload when the diagram type's code fails to load", async () => {
    // GIVEN
    loadMock.mockRejectedValueOnce(new TypeError("Failed to fetch dynamically imported module"));

    // WHEN
    const component = await render(<MermaidDiagram code={'pie\n  "A" : 1'} />);

    // THEN
    await expect
      .element(component.getByText("Could not load the diagram. Reload the page to try again."))
      .toBeVisible();
    expect(component.container.querySelector('button[aria-label="Zoom in"]')).toBeNull();
  });

  test("shows a loading indicator until the diagram type's code has loaded", async () => {
    // GIVEN
    loadMock.mockReturnValueOnce(new Promise(() => {}));

    // WHEN
    const component = await render(<MermaidDiagram code={"journey\n  section A\n    B: 5: C"} />);

    // THEN
    await expect.element(component.getByRole("status")).toBeVisible();
    expect(component.container.querySelector('button[aria-label="Zoom in"]')).toBeNull();
  });

  test("shows a syntax error in a monospace font so its caret points at the column", async () => {
    // WHEN
    const component = await render(
      <MermaidDiagram code={"flowchart LR\n  A --> B\n  B --> [oops"} />
    );

    // THEN
    const message = component.getByText(/^Parse error on line 3/);
    await expect.element(message).toBeVisible();
    expect(getComputedStyle(message.element()).fontFamily).toMatch(/mono/i);
  });

  test("gives each diagram on a page its own SVG id prefix", async () => {
    // GIVEN
    // Only sankey output has ids, and identical code gets identical ids without idPrefix.
    const sankey = "sankey\nA,B,10\nB,C,5";

    // WHEN
    const component = await render(
      <>
        <MermaidDiagram code={sankey} />
        <MermaidDiagram code={sankey} />
      </>
    );

    // THEN
    await expect.poll(() => component.container.querySelectorAll("svg.pele").length).toBe(2);
    const ids = [...component.container.querySelectorAll("svg.pele [id]")].map(({ id }) => id);
    expect(ids.length).toBeGreaterThan(0);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("centres a diagram that is narrower than its container", async () => {
    // WHEN
    const component = await render(
      <div style={{ width: 800 }}>
        <MermaidDiagram code={"flowchart LR\n  A --> B"} />
      </div>
    );

    // THEN
    await expect.poll(() => component.container.querySelector("svg.pele")).toBeTruthy();
    const svg = component.container.querySelector("svg.pele");
    const diagram = svg?.getBoundingClientRect();
    const container = svg?.parentElement?.getBoundingClientRect();
    expect(diagram?.width).toBeLessThan(container?.width ?? 0);
    const centre = (rect?: DOMRect) => (rect ? rect.left + rect.width / 2 : 0);
    expect(Math.abs(centre(diagram) - centre(container))).toBeLessThan(1);
  });

  test("keeps web links in a diagram and drops javascript: links", async () => {
    // WHEN
    const component = await render(
      <MermaidDiagram
        code={
          'flowchart LR\n  A --> B\n  click A "https://example.com" _blank\n  click B "javascript:alert(1)"'
        }
      />
    );

    // THEN
    await expect.poll(() => component.container.querySelector("svg.pele")).toBeTruthy();
    const hrefs = [...component.container.querySelectorAll("svg.pele a")].map((link) =>
      link.getAttribute("href")
    );
    expect(hrefs).toEqual(["https://example.com/"]);
  });

  test("keeps event handlers and javascript: links in labels out of the page", async () => {
    // WHEN
    const component = await render(
      <MermaidDiagram
        code={[
          "flowchart LR",
          '  A["<img src=x onerror=alert(1)>"] --> B["<b onmouseover=alert(1)>bold</b>"]',
          '  B --> C["<a href=\'javascript:alert(1)\'>link</a>"]',
        ].join("\n")}
      />
    );

    // THEN
    await expect.poll(() => component.container.querySelector("svg.pele")).toBeTruthy();
    const elements = [...component.container.querySelectorAll("svg.pele, svg.pele *")];
    expect(component.container.querySelector("svg.pele img")).toBeNull();
    expect(
      elements.flatMap((element) => element.getAttributeNames()).filter((name) => /^on/i.test(name))
    ).toEqual([]);
    expect(
      elements.filter((element) => /javascript:/i.test(element.getAttribute("href") ?? ""))
    ).toEqual([]);
  });

  test("renders a light diagram in the light theme", async () => {
    // WHEN
    await render(<MermaidDiagram code={"graph TD\n  A[Spine] --> B[Leaf]"} />);

    // THEN
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    expect(shapeLuminance()).toBeGreaterThan(0.5);
  });

  test("renders a dark diagram in the dark theme", async () => {
    // GIVEN
    setDarkTheme(true);

    // WHEN
    await render(<MermaidDiagram code={"graph TD\n  A[Spine] --> B[Leaf]"} />);

    // THEN
    await expect.poll(shapeLuminance, { timeout: 15_000 }).not.toBeNull();
    expect(shapeLuminance()).toBeLessThan(0.5);
  });

  test("recolours the mounted diagram in place when the theme changes", async () => {
    // GIVEN
    await render(<MermaidDiagram code={"graph TD\n  A[Spine] --> B[Leaf]"} />);
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
