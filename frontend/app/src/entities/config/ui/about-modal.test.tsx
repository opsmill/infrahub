import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";
import { AboutModal } from "./about-modal";

vi.mock("@/entities/config/ui/queries/get-app-info.query", () => ({
  useGetAppInfo: vi.fn(),
}));

vi.mock("@/entities/config/ui/config-provider", () => ({
  useConfig: vi.fn(),
}));

import { useConfig } from "@/entities/config/ui/config-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

const useGetAppInfoMock = vi.mocked(useGetAppInfo);
const useConfigMock = vi.mocked(useConfig);

function setupMocks() {
  useConfigMock.mockReturnValue({
    installation_type: "community",
  } as any);

  useGetAppInfoMock.mockReturnValue({
    data: { version: "1.8.4", deployment_id: "abc-123-def" },
    isPending: false,
    isError: false,
  } as any);
}

describe("AboutModal", () => {
  test("should display version, edition, and deployment ID when open", async () => {
    // GIVEN
    setupMocks();

    // WHEN
    const component = await render(<AboutModal isOpen={true} onOpenChange={() => {}} />);

    // THEN
    await expect.element(component.getByText("v1.8.4")).toBeVisible();
    await expect.element(component.getByText("community")).toBeVisible();
    await expect.element(component.getByText("abc-123-def")).toBeVisible();
  });

  test("should display N/A when app info fails to load", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({
      installation_type: "community",
    } as any);

    useGetAppInfoMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
    } as any);

    // WHEN
    const component = await render(<AboutModal isOpen={true} onOpenChange={() => {}} />);

    // THEN
    await expect.element(component.getByText("community")).toBeVisible();
    // Version and deployment ID show N/A on error
    const naElements = component.getByText("N/A");
    expect(naElements.elements().length).toBe(2);
  });

  test("should render the Infrahub logo", async () => {
    // GIVEN
    setupMocks();

    // WHEN
    const component = await render(<AboutModal isOpen={true} onOpenChange={() => {}} />);

    // THEN
    await expect.element(component.getByRole("img", { name: "Infrahub logo" })).toBeVisible();
  });

  test("should have copy buttons for each field", async () => {
    // GIVEN
    setupMocks();

    // WHEN
    const component = await render(<AboutModal isOpen={true} onOpenChange={() => {}} />);

    // THEN
    const copyButtons = component.getByRole("button", { name: /copy/i });
    expect(copyButtons.elements().length).toBe(3);
  });

  test("should call onOpenChange when close button is clicked", async () => {
    // GIVEN
    setupMocks();
    const onOpenChange = vi.fn();

    // WHEN
    const component = await render(<AboutModal isOpen={true} onOpenChange={onOpenChange} />);
    await component.getByRole("button", { name: "Close" }).click();

    // THEN
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
