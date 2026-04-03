import { beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

import { render } from "../../../../tests/components/render";
import { ConfigContext } from "./config-provider";
import { AboutModal } from "./about-modal";

vi.mock("@/entities/config/domain/get-app-info", () => ({
  getAppInfo: vi.fn(),
}));

import { getAppInfo } from "@/entities/config/domain/get-app-info";

const getAppInfoMock = vi.mocked(getAppInfo);

function setupMocks({ isError = false } = {}) {
  if (isError) {
    getAppInfoMock.mockRejectedValue(new Error("Failed to fetch"));
  } else {
    getAppInfoMock.mockResolvedValue({
      version: "1.8.4",
      deployment_id: "abc-123-def",
    });
  }
}

const configValue = {
  installation_type: "community",
} as any;

function renderWithConfig(ui: React.ReactElement) {
  return render(<ConfigContext value={configValue}>{ui}</ConfigContext>);
}

describe("AboutModal", () => {
  beforeEach(() => {
    queryClient.clear();
  });

  test("should display version, edition, and deployment ID when open", async () => {
    // GIVEN
    setupMocks();

    // WHEN
    const component = await renderWithConfig(
      <AboutModal isOpen={true} onOpenChange={() => {}} />
    );

    // THEN
    await expect.element(component.getByText("v1.8.4")).toBeVisible();
    await expect.element(component.getByText("community")).toBeVisible();
    await expect.element(component.getByText("abc-123-def")).toBeVisible();
  });

  test("should display N/A when app info fails to load", async () => {
    // GIVEN
    setupMocks({ isError: true });

    // WHEN
    const component = await renderWithConfig(
      <AboutModal isOpen={true} onOpenChange={() => {}} />
    );

    // THEN
    await expect.element(component.getByText("community")).toBeVisible();
    // Wait for error state to resolve, then check both N/A values
    await expect.element(component.getByText("N/A").first()).toBeVisible();
    expect(component.getByText("N/A").elements().length).toBe(2);
  });

  test("should render the Infrahub logo", async () => {
    // GIVEN
    setupMocks();

    // WHEN
    const component = await renderWithConfig(
      <AboutModal isOpen={true} onOpenChange={() => {}} />
    );

    // THEN
    await expect.element(component.getByRole("img", { name: "Infrahub logo" })).toBeVisible();
  });

  test("should have copy buttons for each field", async () => {
    // GIVEN
    setupMocks();

    // WHEN
    const component = await renderWithConfig(
      <AboutModal isOpen={true} onOpenChange={() => {}} />
    );

    // THEN — wait for data to load before counting buttons
    await expect.element(component.getByText("v1.8.4")).toBeVisible();
    const copyButtons = component.getByRole("button", { name: /copy/i });
    expect(copyButtons.elements().length).toBe(3);
  });

  test("should call onOpenChange when close button is clicked", async () => {
    // GIVEN
    setupMocks();
    const onOpenChange = vi.fn();

    // WHEN
    const component = await renderWithConfig(
      <AboutModal isOpen={true} onOpenChange={onOpenChange} />
    );
    await component.getByRole("button", { name: "Close" }).click();

    // THEN
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
