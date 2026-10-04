import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

import { AuthContext, type AuthContextType } from "@/entities/authentication/ui/auth-provider";
import { getAppInfo } from "@/entities/config/domain/use-cases/get-app-info";
import { ConfigContext } from "@/entities/config/ui/config-provider";

import { render } from "../../../../tests/components/render";
import {
  generateLicenseInfo,
  generateLicenseInfoWithoutLicense,
} from "../../../../tests/fake/license";
import { AboutModal } from "./about-modal";

vi.mock("@/entities/config/domain/use-cases/get-app-info");

const config = { installation_type: "community" } as any;

const SIGNED_IN: AuthContextType = {
  accessToken: "token",
  isAuthenticated: true,
  setToken: () => {},
  user: { id: "user-1" },
};

const ANONYMOUS: AuthContextType = {
  accessToken: "",
  isAuthenticated: false,
  setToken: () => {},
  user: null,
};

function renderAboutModal(props = {}, auth: AuthContextType = SIGNED_IN) {
  return render(
    <AuthContext value={auth}>
      <ConfigContext value={config}>
        <AboutModal isOpen={true} onOpenChange={() => {}} {...props} />
      </ConfigContext>
    </AuthContext>
  );
}

describe("AboutModal", () => {
  beforeEach(() => {
    queryClient.clear();
    vi.mocked(getAppInfo).mockResolvedValue({
      version: "1.8.4",
      deployment_id: "abc-123-def",
      license: generateLicenseInfoWithoutLicense(),
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

  test("should add no license rows when no license is required", async () => {
    const component = await renderAboutModal();

    await expect.element(component.getByText("abc-123-def")).toBeVisible();
    expect(component.getByRole("separator").elements().length).toBe(2);
    expect(component.getByText("License", { exact: true }).query()).toBeNull();
  });

  test("should show the license rows when the deployment holds a license", async () => {
    vi.mocked(getAppInfo).mockResolvedValue({
      version: "1.8.4",
      deployment_id: "abc-123-def",
      license: generateLicenseInfo(),
    });

    const component = await renderAboutModal();

    await expect.element(component.getByText("License", { exact: true })).toBeVisible();
    await expect.element(component.getByText("ACME Test Ltd", { exact: true })).toBeVisible();
  });

  test("should show no license rows to an anonymous visitor", async () => {
    vi.mocked(getAppInfo).mockResolvedValue({
      version: "1.8.4",
      deployment_id: "abc-123-def",
      license: generateLicenseInfoWithoutLicense({ state: "unlicensed" }),
    });

    const component = await renderAboutModal({}, ANONYMOUS);

    await expect.element(component.getByText("abc-123-def")).toBeVisible();
    expect(component.getByRole("separator").elements().length).toBe(2);
    expect(component.getByText("License", { exact: true }).query()).toBeNull();
  });

  test("should call onOpenChange when close button is clicked", async () => {
    const onOpenChange = vi.fn();

    const component = await renderAboutModal({ onOpenChange });
    await component.getByRole("button", { name: "Close" }).click();

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
