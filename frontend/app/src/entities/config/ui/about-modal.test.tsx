import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

import { getAppInfo } from "@/entities/config/domain/get-app-info";
import { ConfigContext } from "@/entities/config/ui/config-provider";

import { render } from "../../../../tests/components/render";
import { AboutModal } from "./about-modal";

vi.mock("@/entities/config/domain/get-app-info");

const config = { installation_type: "community" } as any;

function renderAboutModal(props = {}) {
  return render(
    <ConfigContext value={config}>
      <AboutModal isOpen={true} onOpenChange={() => {}} {...props} />
    </ConfigContext>
  );
}

describe("AboutModal", () => {
  beforeEach(() => {
    queryClient.clear();
    vi.mocked(getAppInfo).mockResolvedValue({
      version: "1.8.4",
      deployment_id: "abc-123-def",
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("should display version, edition, and deployment ID", async () => {
    const component = await renderAboutModal();

    await expect.element(component.getByText("v1.8.4")).toBeVisible();
    await expect.element(component.getByText("community")).toBeVisible();
    await expect.element(component.getByText("abc-123-def")).toBeVisible();
  });

  test("should display N/A when app info fails to load", async () => {
    vi.mocked(getAppInfo).mockRejectedValue(new Error("Failed to fetch"));

    const component = await renderAboutModal();

    await expect.element(component.getByText("community")).toBeVisible();
    await expect.element(component.getByText("N/A").first()).toBeVisible();
    expect(component.getByText("N/A").elements().length).toBe(2);
  });

  test("should render the Infrahub logo", async () => {
    const component = await renderAboutModal();

    await expect.element(component.getByRole("img", { name: "Infrahub logo" })).toBeVisible();
  });

  test("should have copy buttons for each field", async () => {
    const component = await renderAboutModal();

    await expect.element(component.getByText("v1.8.4")).toBeVisible();
    const copyButtons = component.getByRole("button", { name: /copy/i });
    expect(copyButtons.elements().length).toBe(3);
  });

  test("should call onOpenChange when close button is clicked", async () => {
    const onOpenChange = vi.fn();

    const component = await renderAboutModal({ onOpenChange });
    await component.getByRole("button", { name: "Close" }).click();

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
