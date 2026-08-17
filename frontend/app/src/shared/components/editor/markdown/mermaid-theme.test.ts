import { describe, expect, test } from "vitest";

import { withMermaidTheme } from "@/shared/components/editor/markdown/mermaid-theme";

describe("withMermaidTheme", () => {
  test("prefixes a mermaid block with the dark directive", () => {
    const out = withMermaidTheme("```mermaid\ngraph TD\n  A --> B\n```", "dark");

    expect(out).toBe('```mermaid\n%%{init: {"theme":"dark"}}%%\ngraph TD\n  A --> B\n```');
  });

  test("uses mermaid's default palette for the light theme", () => {
    const out = withMermaidTheme("```mermaid\ngraph TD\n```", "light");

    expect(out).toContain('"theme":"default"');
  });

  test("themes every block, not just the first", () => {
    const out = withMermaidTheme(
      "```mermaid\ngraph TD\n```\n\ntext\n\n```mermaid\npie\n```",
      "dark"
    );

    expect(out.match(/%%\{init:/g)).toHaveLength(2);
  });

  test("leaves a diagram that already sets its own directive alone", () => {
    // GIVEN an author who chose a palette deliberately
    const source = '```mermaid\n%%{init: {"theme":"forest"}}%%\ngraph TD\n```';

    // WHEN themed
    // THEN their choice survives and nothing is prepended
    expect(withMermaidTheme(source, "dark")).toBe(source);
  });

  test("leaves a diagram configured by front matter alone", () => {
    const source = "```mermaid\n---\nconfig:\n  theme: forest\n---\ngraph TD\n```";

    expect(withMermaidTheme(source, "dark")).toBe(source);
  });

  test("returns markdown with no mermaid block untouched", () => {
    const source = "# Title\n\n```ts\nconst a = 1;\n```";

    expect(withMermaidTheme(source, "dark")).toBe(source);
  });

  test("handles an indented fence inside a list item", () => {
    const out = withMermaidTheme("- item\n\n  ```mermaid\n  graph TD\n  ```", "dark");

    expect(out).toContain('  %%{init: {"theme":"dark"}}%%');
  });

  test("handles a tilde fence", () => {
    const out = withMermaidTheme("~~~mermaid\ngraph TD\n~~~", "dark");

    expect(out).toContain('~~~mermaid\n%%{init: {"theme":"dark"}}%%');
  });
});
