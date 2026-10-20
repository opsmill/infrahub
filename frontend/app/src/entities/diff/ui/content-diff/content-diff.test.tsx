import type { RenderGutter } from "react-diff-view";
import { describe, expect, test } from "vitest";

import { ContentDiff } from "@/entities/diff/ui/content-diff/content-diff";

import { render } from "../../../../../tests/components/render";

const previousLines = Array.from({ length: 60 }, (_, index) => `line ${index + 1}`);
const newLines = previousLines.map((line) =>
  line === "line 10" || line === "line 50" ? `${line} changed` : line
);

const previousContent = `${previousLines.join("\n")}\n`;
const newContent = `${newLines.join("\n")}\n`;

const renderGutter: RenderGutter = ({ renderDefault }) => renderDefault();

const renderContentDiff = () =>
  render(
    <ContentDiff
      previousContent={previousContent}
      newContent={newContent}
      renderGutter={renderGutter}
      getWidgets={() => ({})}
    />
  );

describe("ContentDiff", () => {
  test("separates two hunks with the range of the second one", async () => {
    // GIVEN
    const expectedHeader = "@@ -47,7 +47,7 @@";

    // WHEN
    const component = await renderContentDiff();

    // THEN
    await expect.element(component.getByText(expectedHeader)).toBeVisible();
    await expect.element(component.getByText("line 30", { exact: true })).not.toBeInTheDocument();
  });

  test("shows the hidden lines right above the next hunk when expanding up", async () => {
    // GIVEN
    const component = await renderContentDiff();

    // WHEN
    await component.getByRole("button", { name: "Expand 20 lines up" }).click();

    // THEN
    await expect.element(component.getByText("line 27", { exact: true }).first()).toBeVisible();
    await expect.element(component.getByText("line 26", { exact: true })).not.toBeInTheDocument();
  });

  test("shows every hidden line at the end of the file when they fit in one step", async () => {
    // GIVEN
    const component = await renderContentDiff();

    // WHEN
    await component.getByRole("button", { name: "Expand 7 hidden lines" }).click();

    // THEN
    await expect.element(component.getByText("line 60", { exact: true }).first()).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Expand 7 hidden lines" }))
      .not.toBeInTheDocument();
  });
});
