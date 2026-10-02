import { describe, expect, test } from "vitest";

import { DataViewer } from "@/shared/components/data-viewer/data-viewer";

import { render } from "../../../../tests/components/render";

const SVG_CONTENT =
  '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="red"/></svg>';

// The library's default zoom-in step multiplies the scale by e^0.5 (about 1.65), so this waits out the zoom animation.
const SETTLED_ZOOM_IN_RATIO = 1.6;

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

  test("stretches the svg viewport to the height available to the viewer", async () => {
    // WHEN
    const component = await render(
      <div className="flex h-150 flex-col">
        <DataViewer data={SVG_CONTENT} contentType="image/svg+xml" />
      </div>
    );

    // THEN
    const viewport = component.container.querySelector(".react-transform-wrapper");
    await expect.poll(() => viewport?.getBoundingClientRect().height ?? 0).toBeGreaterThan(400);
  });

  test("zooms in around the svg center", async () => {
    // GIVEN
    const component = await render(
      <div className="flex h-150 flex-col">
        <DataViewer data={SVG_CONTENT} contentType="image/svg+xml" />
      </div>
    );
    const image = component.getByRole("img", { name: "svg-image" }).element();
    await expect.poll(() => image.getBoundingClientRect().height).toBeGreaterThan(0);
    const before = image.getBoundingClientRect();

    // WHEN
    await component.getByRole("button", { name: "Zoom in" }).click();

    // THEN
    await expect
      .poll(() => image.getBoundingClientRect().height)
      .toBeGreaterThan(before.height * SETTLED_ZOOM_IN_RATIO);
    const after = image.getBoundingClientRect();
    expect(Math.abs(getCenterY(after) - getCenterY(before))).toBeLessThan(5);
  });
});

function getCenterY(rect: DOMRect): number {
  return rect.top + rect.height / 2;
}
