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

import { useConfig } from "@/entities/config/ui/config-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

const mockWriteText = vi.fn().mockResolvedValue(undefined);
Object.assign(navigator, {
  clipboard: { writeText: mockWriteText },
});

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
  test("should not display version or error while loading", async () => {
    // WHEN
    const component = await render(
      <AppVersion data={undefined} isPending={true} isError={false} />
    );

    // THEN
    expect(component.getByText("N/A").query()).toBeNull();
    expect(component.getByText(/v\d/).query()).toBeNull();
  });

  test('should display "N/A" on error', async () => {
    // WHEN
    const component = await render(
      <AppVersion data={undefined} isPending={false} isError={true} />
    );

    // THEN
    await expect.element(component.getByText("N/A")).toBeVisible();
  });

  test("should display version when loaded successfully", async () => {
    // WHEN
    const component = await render(
      <AppVersion
        data={{ version: "1.2.3", deployment_id: "abc-123" }}
        isPending={false}
        isError={false}
      />
    );

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
      data: { version: "1.2.3", deployment_id: "abc-123" },
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

  test("should show 'Copied!' and copy UUID to clipboard when clicked", async () => {
    // GIVEN
    mockWriteText.mockClear();
    useConfigMock.mockReturnValue({
      installation_type: "community",
      main_menu_mode: "default",
      main_menu_size: 14,
      experimental_features: {},
    } as any);

    useGetAppInfoMock.mockReturnValue({
      data: {
        version: "1.2.3",
        deployment_id: "d4e5f6a7-b8c9-1234-5678-abcdef012345",
      },
      isPending: false,
      isError: false,
    } as any);

    // WHEN
    const component = await render(<AppInfo />);
    const toggle = component.getByTestId("app-info-toggle");
    await toggle.click();

    // THEN
    await expect.element(component.getByText("Copied!")).toBeVisible();
    expect(mockWriteText).toHaveBeenCalledWith("d4e5f6a7-b8c9-1234-5678-abcdef012345");
  });

  test("should show UUID with prefix after 'Copied!' fades", async () => {
    // GIVEN
    vi.useFakeTimers();
    useConfigMock.mockReturnValue({
      installation_type: "community",
      main_menu_mode: "default",
      main_menu_size: 14,
      experimental_features: {},
    } as any);

    useGetAppInfoMock.mockReturnValue({
      data: {
        version: "1.2.3",
        deployment_id: "d4e5f6a7-b8c9-1234-5678-abcdef012345",
      },
      isPending: false,
      isError: false,
    } as any);

    // WHEN
    const component = await render(<AppInfo />);
    const toggle = component.getByTestId("app-info-toggle");
    await toggle.click();
    vi.advanceTimersByTime(2000);

    // THEN
    await expect
      .element(component.getByText("UUID: d4e5f6a7-b8c9-1234-5678-abcdef012345"))
      .toBeVisible();

    vi.useRealTimers();
  });

  test("should toggle back to default info line when clicked twice", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({
      installation_type: "community",
      main_menu_mode: "default",
      main_menu_size: 14,
      experimental_features: {},
    } as any);

    useGetAppInfoMock.mockReturnValue({
      data: {
        version: "1.2.3",
        deployment_id: "d4e5f6a7-b8c9-1234-5678-abcdef012345",
      },
      isPending: false,
      isError: false,
    } as any);

    // WHEN
    const component = await render(<AppInfo />);
    const toggle = component.getByTestId("app-info-toggle");
    await toggle.click();
    await toggle.click();

    // THEN
    await expect
      .element(component.getByText("Infrahub - Community Edition - v1.2.3"))
      .toBeVisible();
  });

  test("should not be interactive when API request fails", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({
      installation_type: "community",
      main_menu_mode: "default",
      main_menu_size: 14,
      experimental_features: {},
    } as any);

    useGetAppInfoMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
    } as any);

    // WHEN
    const component = await render(<AppInfo />);
    const toggle = component.getByTestId("app-info-toggle");

    // THEN
    await expect.element(toggle).not.toHaveAttribute("role", "button");
  });

  test("should show N/A when deployment_id is empty in toggled state", async () => {
    // GIVEN
    mockWriteText.mockClear();
    useConfigMock.mockReturnValue({
      installation_type: "community",
      main_menu_mode: "default",
      main_menu_size: 14,
      experimental_features: {},
    } as any);

    useGetAppInfoMock.mockReturnValue({
      data: { version: "1.2.3", deployment_id: "" },
      isPending: false,
      isError: false,
    } as any);

    // WHEN
    const component = await render(<AppInfo />);
    const toggle = component.getByTestId("app-info-toggle");
    await toggle.click();

    // THEN
    await expect.element(component.getByText("N/A")).toBeVisible();
    expect(mockWriteText).not.toHaveBeenCalled();
  });
});
