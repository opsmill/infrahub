import { describe, expect, test } from "vitest";

import {
  DatePreferencesContext,
  type ResolvedDatePreferences,
} from "@/shared/context/date-preferences-context";

import { AuthContext, type AuthContextType } from "@/entities/authentication/ui/auth-provider";
import type { LicenseInfo } from "@/entities/license/domain/model/license";

import { render } from "../../../../tests/components/render";
import {
  generateLicenseInfo,
  generateLicenseInfoWithoutLicense,
} from "../../../../tests/fake/license";
import { LicenseAboutRows } from "./license-about-rows";

// A zone east of UTC, where the instant before the license ends already falls on the next day.
const AUCKLAND_PREFS: ResolvedDatePreferences = {
  pattern: "yyyy-MM-dd HH:mm",
  timezone: "Pacific/Auckland",
};

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

function renderRows(license: LicenseInfo | null | undefined, auth: AuthContextType = SIGNED_IN) {
  return render(
    <AuthContext value={auth}>
      <DatePreferencesContext value={AUCKLAND_PREFS}>
        <LicenseAboutRows license={license} />
      </DatePreferencesContext>
    </AuthContext>
  );
}

describe("LicenseAboutRows", () => {
  test("shows the customer, type, tiers and end date of a commercial license", async () => {
    // GIVEN
    const license = generateLicenseInfo({ days_remaining: 200 });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect.element(component.getByText("ACME Test Ltd", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Commercial", { exact: true })).toBeVisible();
    await expect.element(component.getByText("medium", { exact: true })).toBeVisible();
    await expect.element(component.getByText("advanced", { exact: true })).toBeVisible();
    await expect
      .element(component.getByText("2027-09-29 (200 days left)", { exact: true }))
      .toBeVisible();
  });

  test("labels each license row", async () => {
    // GIVEN
    const license = generateLicenseInfo();

    // WHEN
    const component = await renderRows(license);

    // THEN
    for (const label of ["License", "Type", "Product tier", "Support tier", "Ends"]) {
      await expect.element(component.getByText(label, { exact: true })).toBeVisible();
    }
  });

  test("shows the days left in the type of an evaluation license", async () => {
    // GIVEN
    const license = generateLicenseInfo({ license_type: "evaluation", days_remaining: 45 });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect
      .element(component.getByText("Evaluation license, 45 days left", { exact: true }))
      .toBeVisible();
  });

  test("treats a license type it does not know as commercial", async () => {
    // GIVEN
    const license = generateLicenseInfo({ license_type: "partner" });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect.element(component.getByText("Commercial", { exact: true })).toBeVisible();
  });

  test("shows how long ago an expired license ended", async () => {
    // GIVEN
    const license = generateLicenseInfo({
      state: "expired",
      days_remaining: null,
      days_since_expiry: 4,
    });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect
      .element(component.getByText("2027-09-29 (expired 4 days ago)", { exact: true }))
      .toBeVisible();
  });

  test("reads expired today during the first day after the license ended", async () => {
    // GIVEN
    const license = generateLicenseInfo({
      state: "expired",
      days_remaining: null,
      days_since_expiry: 0,
    });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect
      .element(component.getByText("2027-09-29 (expired today)", { exact: true }))
      .toBeVisible();
  });

  test("uses the singular for a single day", async () => {
    // GIVEN
    const license = generateLicenseInfo({
      state: "expiring",
      license_type: "evaluation",
      days_remaining: 1,
    });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect
      .element(component.getByText("Evaluation license, 1 day left", { exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByText("2027-09-29 (1 day left)", { exact: true }))
      .toBeVisible();
  });

  test("shows the end date as the last day the license covers in UTC", async () => {
    // GIVEN
    const license = generateLicenseInfo({ ends_at: "2027-03-01T00:00:00Z", days_remaining: 30 });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect
      .element(component.getByText("2027-02-28 (30 days left)", { exact: true }))
      .toBeVisible();
  });

  test("shows a single row when no license is installed", async () => {
    // GIVEN
    const license = generateLicenseInfoWithoutLicense({ state: "unlicensed" });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect.element(component.getByText("License", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Not installed", { exact: true })).toBeVisible();
    expect(component.getByText("Type", { exact: true }).query()).toBeNull();
  });

  test("shows a single row when the license could not be verified", async () => {
    // GIVEN
    const license = generateLicenseInfoWithoutLicense({
      state: "invalid",
      reason: "bad_signature",
    });

    // WHEN
    const component = await renderRows(license);

    // THEN
    await expect.element(component.getByText("License", { exact: true })).toBeVisible();
    await expect
      .element(component.getByText("Could not be verified", { exact: true }))
      .toBeVisible();
    expect(component.getByText("bad_signature").query()).toBeNull();
  });

  test("renders nothing for an anonymous visitor", async () => {
    // GIVEN
    const license = generateLicenseInfoWithoutLicense({ state: "unlicensed" });

    // WHEN
    const component = await renderRows(license, ANONYMOUS);

    // THEN
    expect(component.getByText("License", { exact: true }).query()).toBeNull();
    expect(component.getByRole("separator").query()).toBeNull();
  });

  test.each([
    { name: "null", license: null },
    { name: "undefined", license: undefined },
  ])("renders nothing when the license object is $name", async ({ license }) => {
    // GIVEN
    const auth = SIGNED_IN;

    // WHEN
    const component = await renderRows(license, auth);

    // THEN
    expect(component.getByText("License", { exact: true }).query()).toBeNull();
    expect(component.getByRole("separator").query()).toBeNull();
  });

  test("renders nothing when no license is required", async () => {
    // GIVEN
    const license = generateLicenseInfoWithoutLicense();

    // WHEN
    const component = await renderRows(license);

    // THEN
    expect(component.getByText("License", { exact: true }).query()).toBeNull();
    expect(component.getByRole("separator").query()).toBeNull();
  });
});
