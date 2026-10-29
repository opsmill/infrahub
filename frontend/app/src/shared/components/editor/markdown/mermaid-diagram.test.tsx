import type * as Pele from "pele/lazy";
import { describe, expect, test, vi } from "vitest";

import { MermaidDiagram } from "@/shared/components/editor/markdown/mermaid-diagram";

import { render } from "../../../../../tests/components/render";

const { loadMock } = vi.hoisted(() => ({ loadMock: vi.fn() }));

// Partial: only the loader is replaced, and it calls the real one unless a test overrides it.
// The component keeps one load per diagram type, so each test uses a different type.
vi.mock("pele/lazy", async (importOriginal) => {
  const actual = await importOriginal<typeof Pele>();
  loadMock.mockImplementation(actual.load);
  return { ...actual, load: loadMock };
});

describe("MermaidDiagram", () => {
  test("asks for a reload when the diagram type's code fails to load", async () => {
    // GIVEN
    loadMock.mockRejectedValueOnce(new TypeError("Failed to fetch dynamically imported module"));

    // WHEN
    const component = await render(<MermaidDiagram source={'pie\n  "A" : 1'} />);

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
    const component = await render(<MermaidDiagram source={"journey\n  section A\n    B: 5: C"} />);

    // THEN
    await expect.element(component.getByRole("status")).toBeVisible();
    expect(component.container.querySelector('button[aria-label="Zoom in"]')).toBeNull();
  });

  test("shows a syntax error in a monospace font so its caret points at the column", async () => {
    // WHEN
    const component = await render(
      <MermaidDiagram source={"flowchart LR\n  A --> B\n  B --> [oops"} />
    );

    // THEN
    const message = () => component.container.querySelector(".mermaid-error");
    await expect.poll(() => message()?.textContent ?? "").toMatch(/^Parse error on line 3/);
    expect(getComputedStyle(message() as Element).fontFamily).toMatch(/mono/i);
  });

  test("gives each diagram on a page its own SVG id prefix", async () => {
    // GIVEN
    // Sankey links reference gradients by id, and the ids derive from the diagram's content.
    const sankey = "sankey\nA,B,10\nB,C,5";

    // WHEN
    const component = await render(
      <>
        <MermaidDiagram source={sankey} />
        <MermaidDiagram source={sankey} />
      </>
    );

    // THEN
    await expect.poll(() => component.container.querySelectorAll("svg.pele").length).toBe(2);
    const ids = [...component.container.querySelectorAll("svg.pele [id]")].map(({ id }) => id);
    expect(ids.length).toBeGreaterThan(0);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
