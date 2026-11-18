import { afterEach, describe, expect, test, vi } from "vitest";

import { ReactAriaRouterProvider } from "@/app/providers/react-aria-router-provider";

import { SidebarProvider } from "@/shared/components/layout/sidebar";

import { SidebarMenuSectionObject } from "@/entities/navigation/ui/sidebar/sidebar-menu-section-object";

import { render } from "../../../../../tests/components/render";
import { generateMenuItem } from "../../../../../tests/fake/menu";

const items = [
  generateMenuItem({
    label: "Device Management",
    path: "",
    children: [
      generateMenuItem({
        label: "Device",
        children: [generateMenuItem({ label: "Interface" })],
      }),
      generateMenuItem({
        label: "Circuit management",
        path: "",
        children: [generateMenuItem({ label: "Circuit" })],
      }),
      generateMenuItem({ label: "Platform" }),
    ],
  }),
];

const renderSection = () =>
  render(
    <ReactAriaRouterProvider>
      <SidebarProvider>
        <SidebarMenuSectionObject items={items} />
      </SidebarProvider>
    </ReactAriaRouterProvider>
  );

describe("SidebarMenuSectionObject", () => {
  afterEach(() => {
    localStorage.removeItem("sidebar_state");
    vi.restoreAllMocks();
  });

  test("lists a group's nested items as links, expanded", async () => {
    // GIVEN
    const section = await renderSection();

    // WHEN
    await section.getByRole("button", { name: "Device Management" }).click();

    // THEN
    await expect
      .element(section.getByRole("link", { name: "Device", exact: true }))
      .toHaveAttribute("href", "/objects/Device");
    await expect
      .element(section.getByRole("link", { name: "Interface" }))
      .toHaveAttribute("href", "/objects/Interface");
  });

  test("shows a group without its own page as plain text", async () => {
    // GIVEN
    const section = await renderSection();

    // WHEN
    await section.getByRole("button", { name: "Device Management" }).click();

    // THEN
    await expect.element(section.getByText("Circuit management")).toBeVisible();
    expect(section.getByRole("link", { name: "Circuit management" }).query()).toBeNull();
  });

  test("collapses a nested group without closing the menu", async () => {
    // GIVEN
    const section = await renderSection();
    await section.getByRole("button", { name: "Device Management" }).click();
    await expect.element(section.getByRole("link", { name: "Interface" })).toBeVisible();

    // WHEN
    await section.getByRole("button", { name: "Collapse Device" }).click();

    // THEN
    expect(section.getByRole("link", { name: "Interface" }).query()).toBeNull();
    await expect.element(section.getByRole("link", { name: "Platform" })).toBeVisible();
  });

  test("closes the menu after following a link", async () => {
    // GIVEN
    const section = await renderSection();
    await section.getByRole("button", { name: "Device Management" }).click();

    // WHEN
    await section.getByRole("link", { name: "Platform" }).click();

    // THEN
    await expect.poll(() => window.location.pathname).toBe("/objects/Platform");
    await expect
      .element(section.getByRole("dialog", { name: "Device Management" }))
      .not.toBeInTheDocument();
  });

  test("names the menu after its group when the sidebar is collapsed", async () => {
    // GIVEN
    localStorage.setItem("sidebar_state", "collapsed");
    const section = await renderSection();

    // WHEN
    await section.getByRole("button", { name: "Device Management" }).click();

    // THEN
    await expect.element(section.getByRole("dialog", { name: "Device Management" })).toBeVisible();
  });

  test("opens a menu holding an item without a label without accessibility warnings", async () => {
    // GIVEN
    const warn = vi.spyOn(console, "warn");
    const unlabelled = {
      ...generateMenuItem({ label: "Unlabelled" }),
      label: "",
      name: "Unlabelled",
    };
    const section = await render(
      <ReactAriaRouterProvider>
        <SidebarProvider>
          <SidebarMenuSectionObject
            items={[generateMenuItem({ label: "Organization", children: [unlabelled] })]}
          />
        </SidebarProvider>
      </ReactAriaRouterProvider>
    );

    // WHEN
    await section.getByRole("button", { name: "Organization" }).click();

    // THEN
    await expect.element(section.getByRole("treegrid", { name: "Organization" })).toBeVisible();
    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining("textValue"));
  });
});
