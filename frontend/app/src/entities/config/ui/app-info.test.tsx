import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";
import { AppInfo, AppInstallationType, AppVersion } from "./app-info";

// Mock the useGetAppInfo hook
vi.mock("@/entities/config/ui/queries/get-app-info.query", () => ({
  useGetAppInfo: vi.fn(),
}));

// Mock the config provider
vi.mock("@/entities/config/ui/config-provider", () => ({
  useConfig: vi.fn(),
}));

import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";
import { useConfig } from "@/entities/config/ui/config-provider";

describe("AppInstallationType", () => {
  const useConfigMock = vi.mocked(useConfig);

  test("should display capitalized installation type with Edition suffix", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({
      installation_type: "community",
      main_menu_mode: "default",
      main_menu_size: 14,
      experimental_features: {},
    } as any);

    // WHEN
    const component = await render(<AppInstallationType />);

    // THEN
    await expect.element(component.getByText("Community Edition")).toBeVisible();
  });

  test("should handle enterprise installation type", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({
      installation_type: "enterprise",
      main_menu_mode: "default",
      main_menu_size: 14,
      experimental_features: {},
    } as any);

    // WHEN
    const component = await render(<AppInstallationType />);

    // THEN
    await expect.element(component.getByText("Enterprise Edition")).toBeVisible();
  });
});

describe("AppVersion", () => {
  const useGetAppInfoMock = vi.mocked(useGetAppInfo);

  test("should not display version or error while loading", async () => {
    // GIVEN
    useGetAppInfoMock.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
    } as any);

    // WHEN
    const component = await render(<AppVersion />);

    // THEN
    // Version text and error state are not visible while loading
    expect(component.getByText("N/A").query()).toBeNull();
    expect(component.getByText(/v\d/).query()).toBeNull();
  });

  test('should display "N/A" on error', async () => {
    // GIVEN
    useGetAppInfoMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
    } as any);

    // WHEN
    const component = await render(<AppVersion />);

    // THEN
    await expect.element(component.getByText("N/A")).toBeVisible();
  });

  test("should display version when loaded successfully", async () => {
    // GIVEN
    useGetAppInfoMock.mockReturnValue({
      data: { version: "1.2.3" },
      isPending: false,
      isError: false,
    } as any);

    // WHEN
    const component = await render(<AppVersion />);

    // THEN
    await expect.element(component.getByText("v1.2.3")).toBeVisible();
  });
});

describe("AppInfo", () => {
  const useGetAppInfoMock = vi.mocked(useGetAppInfo);
  const useConfigMock = vi.mocked(useConfig);

  test("should render complete app info with all components", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({
      installation_type: "community",
      main_menu_mode: "default",
      main_menu_size: 14,
      experimental_features: {},
    } as any);

    useGetAppInfoMock.mockReturnValue({
      data: { version: "1.2.3" },
      isPending: false,
      isError: false,
    } as any);

    // WHEN
    const component = await render(<AppInfo />);

    // THEN
    await expect
      .element(component.getByText("Infrahub - Community Edition - v1.2.3"))
      .toBeVisible();
  });
});
