import { describe, expect, test } from "vitest";

import { DataViewer } from "@/shared/components/data-viewer/data-viewer";

import { render } from "../../../../tests/components/render";

const SVG_CONTENT =
  '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="red"/></svg>';

describe("DataViewer", () => {
  test("renders an svg with zoom controls", async () => {
    // WHEN
    const component = await render(<DataViewer data={SVG_CONTENT} contentType="image/svg+xml" />);

    // THEN
    await expect.element(component.getByRole("img", { name: "svg-image" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Zoom out" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Reset zoom" })).toBeVisible();
  });

  test("zooms the svg in when pressing zoom in", async () => {
    // GIVEN
    const component = await render(<DataViewer data={SVG_CONTENT} contentType="image/svg+xml" />);
    const content = component.container.querySelector(".react-transform-component");
    const initialTransform = content?.getAttribute("style");

    // WHEN
    await component.getByRole("button", { name: "Zoom in" }).click();

    // THEN
    await expect.poll(() => content?.getAttribute("style")).not.toBe(initialTransform);
  });
});
