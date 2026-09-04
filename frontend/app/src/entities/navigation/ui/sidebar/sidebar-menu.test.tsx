import { beforeEach, describe, expect, test, vi } from "vitest";

import { SidebarContent, SidebarProvider } from "@/shared/components/layout/sidebar";

import { useMenu } from "@/entities/navigation/ui/queries/get-menu.query";
import { SidebarMenu } from "@/entities/navigation/ui/sidebar/sidebar-menu";

import { render } from "../../../../../tests/components/render";
import { generateMenuItems } from "../../../../../tests/fake/menu";

vi.mock("@/entities/navigation/ui/queries/get-menu.query");

/**
 * Shorter than the two menu sections need, so the flex column has to take height away from
 * one of them: a laptop-height window, or a large screen zoomed in.
 */
const SHORT_SIDEBAR_HEIGHT = 320;

/** Below this the object section is too small to read or scroll — the sidebar is unusable. */
const MIN_USABLE_SECTION_HEIGHT = 60;

const renderShortSidebar = () =>
  render(
    <SidebarProvider>
      <div
        className="flex flex-col"
        style={{ height: `${SHORT_SIDEBAR_HEIGHT}px`, width: "16rem" }}
      >
        <SidebarContent>
          <SidebarMenu />
        </SidebarContent>
      </div>
    </SidebarProvider>
  );

const queryOne = (container: Element, selector: string) => {
  const element = container.querySelector(selector);
  if (!element) throw new Error(`expected the sidebar to render ${selector}`);
  return element;
};

/** The Radix viewport that actually clips a section's items. */
const viewportAround = (section: Element) => {
  const viewport = section.closest("[data-radix-scroll-area-viewport]");
  if (!viewport) throw new Error("the section is not rendered inside a ScrollArea");
  return viewport;
};

const objectViewportOf = (container: Element) =>
  viewportAround(queryOne(container, "a[href$='/objects/Objects1']"));

const internalViewportOf = (container: Element) =>
  viewportAround(queryOne(container, "a[href$='/objects/Internal1']"));

const heightOf = (element: Element) => element.getBoundingClientRect().height;

describe("SidebarMenu", () => {
  beforeEach(() => {
    vi.mocked(useMenu).mockReturnValue({
      data: {
        sections: {
          object: generateMenuItems(8, "Objects", { section: "object" }),
          internal: generateMenuItems(8, "Internal", { section: "internal" }),
        },
      },
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useMenu>);
  });

  test("keeps the object section usable when the sidebar is too short for both sections", async () => {
    // GIVEN
    const sidebar = await renderShortSidebar();

    // WHEN
    await expect.element(sidebar.getByText("Objects 1")).toBeVisible();

    // THEN
    expect(heightOf(objectViewportOf(sidebar.container))).toBeGreaterThanOrEqual(
      MIN_USABLE_SECTION_HEIGHT
    );
  });

  test("lets the internal section give up height instead of pinning it to its full size", async () => {
    // GIVEN
    const sidebar = await renderShortSidebar();

    // WHEN
    await expect.element(sidebar.getByText("Internal 1")).toBeVisible();

    // THEN
    const internalViewport = internalViewportOf(sidebar.container);
    expect(heightOf(internalViewport)).toBeLessThan(
      SHORT_SIDEBAR_HEIGHT - MIN_USABLE_SECTION_HEIGHT
    );
    expect(internalViewport.scrollHeight).toBeGreaterThan(heightOf(internalViewport));
  });

  test("scrolls the last object item into view on a short sidebar", async () => {
    // GIVEN
    const sidebar = await renderShortSidebar();
    await expect.element(sidebar.getByText("Objects 8")).toBeVisible();
    const viewport = objectViewportOf(sidebar.container);

    // WHEN
    viewport.scrollTop = viewport.scrollHeight;

    // THEN
    const itemBox = queryOne(
      sidebar.container,
      "a[href$='/objects/Objects8']"
    ).getBoundingClientRect();
    const viewportBox = viewport.getBoundingClientRect();
    expect(itemBox.top).toBeGreaterThanOrEqual(Math.floor(viewportBox.top));
    expect(itemBox.bottom).toBeLessThanOrEqual(Math.ceil(viewportBox.bottom));
  });
});
