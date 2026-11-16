import { describe, expect, test } from "vitest";

import { SidebarProvider } from "@/shared/components/layout/sidebar";

import { SidebarMenuSectionInternal } from "@/entities/navigation/ui/sidebar/sidebar-menu-section-internal";

import { render } from "../../../../../tests/components/render";
import { generateMenuItem } from "../../../../../tests/fake/menu";

const items = [
  generateMenuItem({
    label: "Integrations",
    children: [
      generateMenuItem({ label: "Git Repositories" }),
      generateMenuItem({
        label: "Webhooks",
        children: [generateMenuItem({ label: "Custom Webhooks" })],
      }),
    ],
  }),
];

const renderSection = () =>
  render(
    <SidebarProvider>
      <SidebarMenuSectionInternal items={items} />
    </SidebarProvider>
  );

describe("SidebarMenuSectionInternal", () => {
  test("lists a group's items as links once the group is opened", async () => {
    // GIVEN
    const section = await renderSection();

    // WHEN
    await section.getByRole("button", { name: "Integrations" }).click();

    // THEN
    await expect
      .element(section.getByRole("menuitem", { name: "Git Repositories" }))
      .toHaveAttribute("href", "/objects/GitRepositories");
  });

  test("opens a nested group in a submenu", async () => {
    // GIVEN
    const section = await renderSection();
    await section.getByRole("button", { name: "Integrations" }).click();

    // WHEN
    await section.getByRole("menuitem", { name: "Webhooks" }).click();

    // THEN
    await expect
      .element(section.getByRole("menuitem", { name: "Custom Webhooks" }))
      .toHaveAttribute("href", "/objects/CustomWebhooks");
  });
});
