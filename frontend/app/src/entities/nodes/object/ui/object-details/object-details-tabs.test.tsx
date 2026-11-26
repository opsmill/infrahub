import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

import { render } from "../../../../../../tests/components/render";
import {
  generateCommitsApiResult,
  generateInSyncCommitsResponse,
} from "../../../../../../tests/fake/repository-commit";
import {
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { ObjectDetailsTabs } from "./object-details-tabs";

vi.mock("@/entities/repository/api/get-repository-commits-from-api");
vi.mock("@/entities/nodes/relationships/ui/queries/get-relationship-count.query", () => ({
  useGetRelationshipCount: () => ({ isPending: false, data: 0 }),
}));

const renderTabs = (kind: string, inheritFrom: string[]) => {
  const objectSchema = generateNodeSchema({ kind, inherit_from: inheritFrom, relationships: [] });
  const objectData: NodeObject = { id: "object-1", __typename: kind };
  return render(<ObjectDetailsTabs objectSchema={objectSchema} objectData={objectData} />);
};

const renderOverflowingTabs = () => {
  const relationships = Array.from({ length: 10 }, (_, index) =>
    generateRelationshipSchema({
      name: `relationship_${index}`,
      identifier: `relationship_${index}`,
      label: `Relationship number ${index}`,
      kind: "Generic",
      cardinality: "many",
    })
  );
  const objectSchema = generateNodeSchema({ kind: "LocationSite", relationships });
  const objectData: NodeObject = { id: "object-1", __typename: "LocationSite" };
  return render(
    <div className="w-100">
      <ObjectDetailsTabs objectSchema={objectSchema} objectData={objectData} />
    </div>
  );
};

const tabsViewport = () =>
  document
    .querySelector('[data-testid="object-details-tabs"]')!
    .closest("[data-radix-scroll-area-viewport]")!;

describe("ObjectDetailsTabs", () => {
  beforeEach(() => {
    vi.mocked(getRepositoryCommitsFromApi).mockResolvedValue(
      generateCommitsApiResult(generateInSyncCommitsResponse())
    );
  });

  afterEach(() => {
    vi.resetAllMocks();
    window.history.pushState({}, "", "/");
  });

  test("shows the Commits tab for a repository", async () => {
    // WHEN
    const component = await renderTabs(REPOSITORY_KIND, [GENERIC_REPOSITORY_KIND]);

    // THEN
    await expect.element(component.getByRole("link", { name: /^Commits/ })).toBeVisible();
  });

  test("shows a horizontal scroll bar when the tabs do not fit", async () => {
    // WHEN
    const component = await renderOverflowingTabs();

    // THEN
    await expect.element(component.getByRole("link", { name: "Details" })).toBeVisible();
    const viewport = tabsViewport();
    expect(viewport.scrollWidth).toBeGreaterThan(viewport.clientWidth);

    const horizontalScrollBar = () =>
      viewport.parentElement!.querySelector(':scope > [data-orientation="horizontal"]');
    await expect
      .poll(() => {
        const scrollBar = horizontalScrollBar();
        return scrollBar ? getComputedStyle(scrollBar).display : "absent";
      })
      .not.toMatch(/^(none|absent)$/);

    const detailsTab = component.getByRole("link", { name: "Details" }).element();
    expect(horizontalScrollBar()!.getBoundingClientRect().top).toBeGreaterThanOrEqual(
      detailsTab.getBoundingClientRect().bottom
    );
  });

  test("shows no horizontal scroll bar when the tabs fit", async () => {
    // WHEN
    const component = await renderTabs("BuiltinTag", []);

    // THEN
    await expect.element(component.getByRole("link", { name: "Details" })).toBeVisible();
    const tabs = component.getByTestId("object-details-tabs").element();
    const viewport = tabs.closest("[data-radix-scroll-area-viewport]")!;
    expect(viewport.scrollWidth).toBeLessThanOrEqual(viewport.clientWidth);
    expect(
      viewport.parentElement!.querySelector(':scope > [data-orientation="horizontal"]')
    ).toBeNull();
  });

  test("shows a scroll-right arrow when tabs are hidden on the right", async () => {
    // WHEN
    const component = await renderOverflowingTabs();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Scroll tabs right" }))
      .toBeVisible();
    expect(component.getByRole("button", { name: "Scroll tabs left" }).query()).toBeNull();
  });

  test("scrolls the tabs and shows a scroll-left arrow after the right arrow is clicked", async () => {
    // GIVEN
    const component = await renderOverflowingTabs();
    const rightArrow = component.getByRole("button", { name: "Scroll tabs right" });
    await expect.element(rightArrow).toBeVisible();

    // WHEN
    await rightArrow.click();

    // THEN
    await expect.poll(() => tabsViewport().scrollLeft).toBeGreaterThan(0);
    await expect.element(component.getByRole("button", { name: "Scroll tabs left" })).toBeVisible();
  });

  test("shows no scroll arrows when the tabs fit", async () => {
    // WHEN
    const component = await renderTabs("BuiltinTag", []);

    // THEN
    await expect.element(component.getByRole("link", { name: "Details" })).toBeVisible();
    expect(component.getByRole("button", { name: "Scroll tabs right" }).query()).toBeNull();
    expect(component.getByRole("button", { name: "Scroll tabs left" }).query()).toBeNull();
  });

  test("scrolls the tabs sideways with a vertical mouse wheel", async () => {
    // GIVEN
    const component = await renderOverflowingTabs();
    await expect
      .element(component.getByRole("button", { name: "Scroll tabs right" }))
      .toBeVisible();

    // WHEN
    tabsViewport().dispatchEvent(
      new WheelEvent("wheel", { deltaY: 120, bubbles: true, cancelable: true })
    );

    // THEN
    await expect.poll(() => tabsViewport().scrollLeft).toBeGreaterThan(0);
  });

  test("hands a vertical mouse wheel back to the page when the tabs are scrolled to the right end", async () => {
    // GIVEN
    const component = await renderOverflowingTabs();
    await expect
      .element(component.getByRole("button", { name: "Scroll tabs right" }))
      .toBeVisible();
    const viewport = tabsViewport();
    viewport.scrollLeft = viewport.scrollWidth;
    await expect
      .element(component.getByRole("button", { name: "Scroll tabs right" }))
      .not.toBeInTheDocument();

    // WHEN
    const wheel = new WheelEvent("wheel", { deltaY: 120, bubbles: true, cancelable: true });
    viewport.dispatchEvent(wheel);

    // THEN
    expect(wheel.defaultPrevented).toBe(false);
  });

  test("leaves a Ctrl + mouse wheel to the browser zoom", async () => {
    // GIVEN
    const component = await renderOverflowingTabs();
    await expect
      .element(component.getByRole("button", { name: "Scroll tabs right" }))
      .toBeVisible();

    // WHEN
    const wheel = new WheelEvent("wheel", {
      deltaY: 120,
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    tabsViewport().dispatchEvent(wheel);

    // THEN
    expect(wheel.defaultPrevented).toBe(false);
    expect(tabsViewport().scrollLeft).toBe(0);
  });

  test("scrolls the tabs by whole lines for a mouse wheel that reports lines", async () => {
    // GIVEN
    const component = await renderOverflowingTabs();
    await expect
      .element(component.getByRole("button", { name: "Scroll tabs right" }))
      .toBeVisible();
    const lines = 3;

    // WHEN
    tabsViewport().dispatchEvent(
      new WheelEvent("wheel", {
        deltaY: lines,
        deltaMode: WheelEvent.DOM_DELTA_LINE,
        bubbles: true,
        cancelable: true,
      })
    );

    // THEN
    const lineHeight = Number.parseFloat(getComputedStyle(tabsViewport()).fontSize);
    await expect
      .poll(() => tabsViewport().scrollLeft)
      .toBeGreaterThanOrEqual(lines * lineHeight);
  });

  test("keeps the scroll arrows out of the keyboard tab order", async () => {
    // WHEN
    const component = await renderOverflowingTabs();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Scroll tabs right" }))
      .toHaveAttribute("tabindex", "-1");
  });

  test("keeps a deep-linked tab clear of the edge fade", async () => {
    // GIVEN
    const firstRender = await renderOverflowingTabs();
    const tabUrl = firstRender
      .getByRole("link", { name: /^Relationship number 5/ })
      .element()
      .getAttribute("href")!;
    await firstRender.unmount();
    window.history.pushState({}, "", tabUrl);

    // WHEN
    const component = await renderOverflowingTabs();

    // THEN
    const tab = component.getByRole("link", { name: /^Relationship number 5/ }).element();
    await expect.poll(() => tabsViewport().scrollLeft).toBeGreaterThan(0);
    await expect
      .poll(() => tabsViewport().getBoundingClientRect().right - tab.getBoundingClientRect().right)
      .toBeGreaterThanOrEqual(64);
  });

  test("shows no Commits tab for an object that is not a repository", async () => {
    // WHEN
    const component = await renderTabs("BuiltinTag", []);

    // THEN
    await expect.element(component.getByRole("link", { name: "Details" })).toBeVisible();
    expect(component.getByRole("link", { name: /^Commits/ }).query()).toBeNull();
    expect(getRepositoryCommitsFromApi).not.toHaveBeenCalled();
  });
});
