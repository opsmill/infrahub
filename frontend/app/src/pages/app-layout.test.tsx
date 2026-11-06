import { afterEach, describe, expect, test, vi } from "vitest";

import { useConfig } from "@/entities/config/ui/config-provider";

import { render } from "../../tests/components/render";
import { generateConfigWithInstance } from "../../tests/fake/config";
import { Component as AppLayout } from "./app-layout";

vi.mock("@/entities/config/ui/config-provider");
vi.mock("@/entities/navigation/ui/sidebar/app-sidebar", () => ({
  AppSidebar: () => <nav data-testid="sidebar-stub">sidebar</nav>,
}));
vi.mock("@/entities/navigation/ui/app-header", () => ({
  AppHeader: () => <header data-testid="header-stub">header</header>,
}));

describe("AppLayout", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("renders the instance color bar edge to edge above the padded sidebar and header row", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance("QA", "RED"));

    // WHEN
    const component = await render(<AppLayout />);

    // THEN
    const bar = component.getByTestId("instance-color-bar").element();
    const page = bar.parentElement;
    const paddedContent = bar.nextElementSibling;
    expect(page?.firstElementChild).toBe(bar);
    expect(paddedContent?.classList.contains("p-0.5")).toBe(true);
    expect(paddedContent?.contains(component.getByTestId("sidebar-stub").element())).toBe(true);
    expect(paddedContent?.contains(component.getByTestId("header-stub").element())).toBe(true);
  });

  test("renders no color bar when no instance color is set", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance("QA", null));

    // WHEN
    const component = await render(<AppLayout />);

    // THEN
    await expect.element(component.getByTestId("header-stub")).toBeVisible();
    expect(component.getByTestId("instance-color-bar").query()).toBeNull();
  });
});
