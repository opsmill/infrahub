import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";
import { generateRackR1Elevation } from "../../../../tests/fake/rack-elevation";
import { RackElevationSvg } from "./rack-elevation-svg";

const UNIT_HEIGHT = 24;

const renderSvg = (movingItemId: string | null = null) =>
  render(
    <RackElevationSvg
      elevation={generateRackR1Elevation()}
      footerText="R1 · branch test-branch"
      movingItemId={movingItemId}
      onOpenItem={vi.fn()}
      onStartMove={vi.fn()}
      onSelectUnit={vi.fn()}
    />
  );

const getItemElements = (container: Element, name: string) =>
  Array.from(container.querySelectorAll(`[data-testid="rack-item-${name}"]`));

const getHeight = (element: Element) =>
  Number(element.querySelector("rect")?.getAttribute("height"));

describe("RackElevationSvg", () => {
  test("draws an item over every unit it uses", async () => {
    // WHEN
    const { container } = await renderSvg();

    // THEN
    const [srv1] = getItemElements(container, "srv1");
    const [leaf1] = getItemElements(container, "leaf1");
    expect(srv1?.getAttribute("data-position")).toBe("1");
    expect(getHeight(srv1 as Element)).toBe(2 * UNIT_HEIGHT);
    expect(getHeight(leaf1 as Element)).toBe(UNIT_HEIGHT);
  });

  test("draws a full depth item on both faces and dims the face it is not mounted on", async () => {
    // WHEN
    const { container } = await renderSvg();

    // THEN
    const leaf1 = getItemElements(container, "leaf1");
    expect(leaf1.map((element) => element.getAttribute("data-face"))).toEqual(["front", "rear"]);
    expect(leaf1.map((element) => element.getAttribute("data-dimmed"))).toEqual([null, "true"]);
    expect(leaf1.map((element) => element.getAttribute("data-position"))).toEqual(["12", "12"]);
  });

  test("draws a half depth item on its own face only", async () => {
    // WHEN
    const { container } = await renderSvg();

    // THEN
    const pp1 = getItemElements(container, "pp1");
    expect(pp1).toHaveLength(1);
    expect(pp1[0]?.getAttribute("data-face")).toBe("rear");
    expect(pp1[0]?.getAttribute("data-dimmed")).toBeNull();
  });

  test("shows the full label and the type in a tooltip", async () => {
    // WHEN
    const { container } = await renderSvg();

    // THEN
    const [srv1] = getItemElements(container, "srv1");
    expect(srv1?.querySelector("title")?.textContent).toBe("srv1 · Server 2U");
  });

  test("draws items that are not mounted outside the rack", async () => {
    // WHEN
    const { container } = await renderSvg();

    // THEN
    expect(getItemElements(container, "spare1")).toHaveLength(0);
    expect(getItemElements(container, "pdu1")).toHaveLength(0);
  });

  test("draws a free unit only where no item uses it on that face", async () => {
    // WHEN
    const { container } = await renderSvg();

    // THEN
    expect(container.querySelector('[data-testid="rack-unit-front-5"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="rack-unit-rear-5"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="rack-unit-front-12"]')).toBeNull();
    expect(container.querySelector('[data-testid="rack-unit-rear-12"]')).toBeNull();
    expect(container.querySelector('[data-testid="rack-unit-front-1"]')).toBeNull();
  });

  test("offers every unit as a target while an item is being moved", async () => {
    // WHEN
    const { container } = await renderSvg("item-srv1");

    // THEN
    expect(container.querySelector('[data-testid="rack-unit-front-12"]')).not.toBeNull();
    expect(container.querySelectorAll('[data-testid^="rack-unit-"]')).toHaveLength(24);
  });

  test("numbers the units from 1 at the bottom", async () => {
    // WHEN
    const { container } = await renderSvg();

    // THEN
    const [leaf1] = getItemElements(container, "leaf1");
    const [srv1] = getItemElements(container, "srv1");
    expect(Number(leaf1?.querySelector("rect")?.getAttribute("y"))).toBeLessThan(
      Number(srv1?.querySelector("rect")?.getAttribute("y"))
    );
  });
});
