import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  DatePreferencesContext,
  type ResolvedDatePreferences,
} from "@/shared/context/date-preferences-context";

import { AuthContext, type AuthContextType } from "@/entities/authentication/ui/auth-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";
import type { LicenseInfo } from "@/entities/license/domain/model/license";
import { SUPER_ADMIN } from "@/entities/permission/domain/model/permission";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";

import { render } from "../../../../tests/components/render";
import {
  generateLicenseInfo,
  generateLicenseInfoWithoutLicense,
} from "../../../../tests/fake/license";
import { LicenseBanner } from "./license-banner";

vi.mock("@/entities/config/ui/queries/get-app-info.query", () => ({
  useGetAppInfo: vi.fn(),
}));

vi.mock("@/entities/permission/ui/queries/has-global-permission.query", () => ({
  useHasGlobalPermission: vi.fn(),
}));

type AppInfoResult = ReturnType<typeof useGetAppInfo>;
type PermissionResult = ReturnType<typeof useHasGlobalPermission>;

const DEPLOYMENT_ID = "1f0a6c3e-2b4d-4e8f-9a1b-7c5d3e2f1a0b";

const UNLICENSED_TEXT =
  "Infrahub Enterprise is running without a license. Ask your Infrahub administrator for your organization's license, or contact sales.";

const BAD_SIGNATURE_ADVICE =
  "The license signature does not match its content. Check INFRAHUB_LICENSE_KEY on the servers and task workers.";

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

// A zone east of UTC, where the instant before the license ends already falls on the next day.
const AUCKLAND_PREFS: ResolvedDatePreferences = {
  pattern: "yyyy-MM-dd HH:mm",
  timezone: "Pacific/Auckland",
};

const UNLICENSED_ENFORCED = generateLicenseInfoWithoutLicense({
  state: "unlicensed",
  notice_mode: "enforce",
  banner: { audience: "all_users", dismissible: false, shown_to_all_users_when_enforced: false },
});

const UNLICENSED_FOR_SUPER_ADMINS = generateLicenseInfoWithoutLicense({
  state: "unlicensed",
  banner: { audience: "super_admins", dismissible: true, shown_to_all_users_when_enforced: true },
});

const EXPIRING_FOR_SUPER_ADMINS = generateLicenseInfo({
  state: "expiring",
  days_remaining: 12,
  banner: { audience: "super_admins", dismissible: true, shown_to_all_users_when_enforced: false },
});

const INVALID_ENFORCED = generateLicenseInfoWithoutLicense({
  state: "invalid",
  reason: "bad_signature",
  notice_mode: "enforce",
  banner: { audience: "all_users", dismissible: false, shown_to_all_users_when_enforced: false },
});

function mockAppInfo(result: { data?: unknown; isError?: boolean }) {
  vi.mocked(useGetAppInfo).mockReturnValue({
    isError: false,
    ...result,
  } as unknown as AppInfoResult);
}

function mockAppInfoLicense(license: LicenseInfo | null) {
  mockAppInfo({ data: { version: "1.12.0", deployment_id: DEPLOYMENT_ID, license } });
}

function mockSuperAdmin(isSuperAdmin: boolean) {
  vi.mocked(useHasGlobalPermission).mockReturnValue({
    data: isSuperAdmin,
    isSuccess: true,
  } as unknown as PermissionResult);
}

function renderBanner(auth: AuthContextType = SIGNED_IN) {
  return render(
    <AuthContext value={auth}>
      <DatePreferencesContext value={AUCKLAND_PREFS}>
        <LicenseBanner />
      </DatePreferencesContext>
    </AuthContext>
  );
}

beforeEach(() => {
  sessionStorage.clear();
  mockSuperAdmin(false);
});

afterEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

describe("LicenseBanner", () => {
  test("shows the banner to every signed-in user when the audience is all users", async () => {
    // GIVEN
    mockAppInfoLicense(UNLICENSED_ENFORCED);

    // WHEN
    const component = await renderBanner();

    // THEN
    const banner = component.getByRole("region", { name: "License notice" });
    await expect.element(banner.getByText(UNLICENSED_TEXT, { exact: true })).toBeVisible();
  });

  test("shows nothing to a visitor who is not signed in, even with a license cached", async () => {
    // GIVEN
    mockAppInfoLicense(UNLICENSED_ENFORCED);

    // WHEN
    const component = await renderBanner(ANONYMOUS);

    // THEN
    expect(component.getByRole("region", { name: "License notice" }).query()).toBeNull();
  });

  test("shows a super-admin banner when the permission check says super-admin", async () => {
    // GIVEN
    mockAppInfoLicense(EXPIRING_FOR_SUPER_ADMINS);
    mockSuperAdmin(true);

    // WHEN
    const component = await renderBanner();

    // THEN
    await expect
      .element(
        component.getByText("Your license expires in 12 days, on 2027-09-29.", { exact: true })
      )
      .toBeVisible();
    expect(useHasGlobalPermission).toHaveBeenCalledWith(SUPER_ADMIN);
  });

  test("shows nothing to a regular user when the audience is super-admins", async () => {
    // GIVEN
    mockAppInfoLicense(EXPIRING_FOR_SUPER_ADMINS);
    mockSuperAdmin(false);

    // WHEN
    const component = await renderBanner();

    // THEN
    expect(component.getByRole("region", { name: "License notice" }).query()).toBeNull();
  });

  test("shows nothing while the super-admin permission check is pending", async () => {
    // GIVEN
    mockAppInfoLicense(EXPIRING_FOR_SUPER_ADMINS);
    vi.mocked(useHasGlobalPermission).mockReturnValue({
      data: true,
      isSuccess: false,
      isPending: true,
    } as unknown as PermissionResult);

    // WHEN
    const component = await renderBanner();

    // THEN
    expect(component.getByRole("region", { name: "License notice" }).query()).toBeNull();
  });

  test("shows nothing and checks no permission when the license needs no attention", async () => {
    // GIVEN
    mockAppInfoLicense(
      generateLicenseInfo({
        banner: { audience: "none", dismissible: false, shown_to_all_users_when_enforced: false },
      })
    );
    mockSuperAdmin(true);

    // WHEN
    const component = await renderBanner();

    // THEN
    expect(component.getByRole("region", { name: "License notice" }).query()).toBeNull();
    expect(useHasGlobalPermission).not.toHaveBeenCalled();
  });

  test.each([
    { name: "null", data: { version: "1.12.0", deployment_id: DEPLOYMENT_ID, license: null } },
    { name: "missing", data: { version: "1.12.0", deployment_id: DEPLOYMENT_ID } },
  ])("shows nothing when the license object is $name", async ({ data }) => {
    // GIVEN
    mockAppInfo({ data });

    // WHEN
    const component = await renderBanner();

    // THEN
    expect(component.getByRole("region", { name: "License notice" }).query()).toBeNull();
  });

  test.each([
    { name: "before any answer", data: undefined },
    {
      name: "after an earlier answer",
      data: { version: "1.12.0", deployment_id: DEPLOYMENT_ID, license: UNLICENSED_ENFORCED },
    },
  ])("shows nothing when the app info request fails $name", async ({ data }) => {
    // GIVEN
    mockAppInfo({ data, isError: true });

    // WHEN
    const component = await renderBanner();

    // THEN
    expect(component.getByRole("region", { name: "License notice" }).query()).toBeNull();
  });

  test("shows the deployment ID with a copy action when no license is installed", async () => {
    // GIVEN
    mockAppInfoLicense(UNLICENSED_ENFORCED);

    // WHEN
    const component = await renderBanner();

    // THEN
    await expect
      .element(component.getByText(`Deployment ID: ${DEPLOYMENT_ID}`, { exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Copy deployment ID" }))
      .toBeVisible();
  });

  test("shows no deployment ID when a license is installed", async () => {
    // GIVEN
    mockAppInfoLicense(EXPIRING_FOR_SUPER_ADMINS);
    mockSuperAdmin(true);

    // WHEN
    const component = await renderBanner();

    // THEN
    await expect.element(component.getByRole("region", { name: "License notice" })).toBeVisible();
    expect(component.getByText(/Deployment ID/).query()).toBeNull();
  });

  test("hides a dismissible banner when the user dismisses it", async () => {
    // GIVEN
    mockAppInfoLicense(EXPIRING_FOR_SUPER_ADMINS);
    mockSuperAdmin(true);
    const component = await renderBanner();

    // WHEN
    await component.getByRole("button", { name: "Dismiss license notice" }).click();

    // THEN
    await expect
      .element(component.getByRole("region", { name: "License notice" }))
      .not.toBeInTheDocument();
  });

  test("shows a banner that is not dismissible even after the same notice was dismissed", async () => {
    // GIVEN
    mockAppInfoLicense(UNLICENSED_FOR_SUPER_ADMINS);
    mockSuperAdmin(true);
    const quiet = await renderBanner();
    await quiet.getByRole("button", { name: "Dismiss license notice" }).click();
    await expect
      .element(quiet.getByRole("region", { name: "License notice" }))
      .not.toBeInTheDocument();
    await quiet.unmount();

    // WHEN
    mockAppInfoLicense(UNLICENSED_ENFORCED);
    const enforced = await renderBanner();

    // THEN
    await expect.element(enforced.getByRole("region", { name: "License notice" })).toBeVisible();
  });

  test("offers no dismissal when the banner is not dismissible", async () => {
    // GIVEN
    mockAppInfoLicense(UNLICENSED_ENFORCED);

    // WHEN
    const component = await renderBanner();

    // THEN
    await expect.element(component.getByRole("region", { name: "License notice" })).toBeVisible();
    expect(component.getByRole("button", { name: "Dismiss license notice" }).query()).toBeNull();
  });

  test.each([
    {
      name: "super-admin banner",
      license: generateLicenseInfoWithoutLicense({
        state: "invalid",
        reason: "bad_signature",
        banner: {
          audience: "super_admins",
          dismissible: true,
          shown_to_all_users_when_enforced: true,
        },
      }),
    },
    { name: "banner shown to every user", license: INVALID_ENFORCED },
  ])(
    "explains why the license could not be verified to a super-admin in a $name",
    async ({ license }) => {
      // GIVEN
      mockAppInfoLicense(license);
      mockSuperAdmin(true);

      // WHEN
      const component = await renderBanner();

      // THEN
      await expect
        .element(component.getByText(BAD_SIGNATURE_ADVICE, { exact: true }))
        .toBeVisible();
    }
  );

  test("does not explain why the license could not be verified to a regular user", async () => {
    // GIVEN
    mockAppInfoLicense(INVALID_ENFORCED);
    mockSuperAdmin(false);

    // WHEN
    const component = await renderBanner();

    // THEN
    await expect
      .element(component.getByText("The installed license could not be verified.", { exact: true }))
      .toBeVisible();
    expect(component.getByText(/Check INFRAHUB_LICENSE_KEY/).query()).toBeNull();
  });
});
