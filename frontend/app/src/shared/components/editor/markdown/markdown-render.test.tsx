import { describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { MarkdownRender } from "./markdown-render";

describe("MarkdownRender Component", () => {
  test("renders markdown text correctly", async () => {
    // GIVEN
    const markdownText = "**bold** and *italic*";

    // WHEN
    const component = await render(<MarkdownRender markdownText={markdownText} />);

    // THEN
    await expect.element(component.getByText("bold")).toBeVisible();
    await expect.element(component.getByText("italic")).toBeVisible();
  });

  test("renders single newlines as line breaks", async () => {
    // GIVEN
    const markdownText = "line one\nline two\nline three";

    // WHEN
    const component = await render(<MarkdownRender markdownText={markdownText} />);

    // THEN
    const brElements = component.container.querySelectorAll("br");
    expect(brElements.length).toBe(2);
  });

  test("renders empty string without errors", async () => {
    // GIVEN
    const markdownText = "";

    // WHEN
    const component = await render(<MarkdownRender markdownText={markdownText} />);

    // THEN
    const markdownDiv = component.container.querySelector(".markdown");
    expect(markdownDiv).not.toBeNull();
  });

  test("applies custom className", async () => {
    // GIVEN
    const className = "custom-class";

    // WHEN
    const component = await render(<MarkdownRender markdownText="test" className={className} />);

    // THEN
    const markdownDiv = component.container.querySelector(".markdown");
    expect(markdownDiv?.classList.contains("custom-class")).toBe(true);
  });

  test("renders a mermaid code block as an inline SVG", async () => {
    // GIVEN
    const markdownText = "```mermaid\ngraph TD;\n  A-->B;\n```";

    // WHEN
    const component = await render(<MarkdownRender markdownText={markdownText} />);

    // THEN
    await expect
      .poll(() => component.container.querySelector("svg"), { timeout: 15_000 })
      .toBeTruthy();
  });

  test("renders zoom controls for a mermaid diagram", async () => {
    // GIVEN
    const markdownText = "```mermaid\ngraph TD;\n  A-->B;\n```";

    // WHEN
    const component = await render(<MarkdownRender markdownText={markdownText} />);

    // THEN
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
  });

  test("shows an error banner when a mermaid diagram is invalid", async () => {
    // GIVEN
    const markdownText = "```mermaid\nnotadiagramtype\n```";

    // WHEN
    const component = await render(<MarkdownRender markdownText={markdownText} />);

    // THEN
    await expect
      .poll(() => component.container.querySelector(".mermaid-error")?.textContent ?? "", {
        timeout: 15_000,
      })
      .not.toBe("");
  });
});
