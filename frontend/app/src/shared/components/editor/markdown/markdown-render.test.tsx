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
});
