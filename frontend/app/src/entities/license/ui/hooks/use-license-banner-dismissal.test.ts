import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { LicenseInfo } from "@/entities/license/domain/model/license";

import {
  generateLicenseInfo,
  generateLicenseInfoWithoutLicense,
} from "../../../../../tests/fake/license";
import { useLicenseBannerDismissal } from "./use-license-banner-dismissal";

const EXPIRING = generateLicenseInfo({ state: "expiring", days_remaining: 12 });
const UNLICENSED = generateLicenseInfoWithoutLicense({ state: "unlicensed" });

async function dismissFor(license: LicenseInfo) {
  const hook = await renderHook(() => useLicenseBannerDismissal(license));
  await hook.act(() => {
    hook.result.current.dismiss();
  });
  await hook.unmount();
}

function blockSessionStorage(method: "getItem" | "setItem") {
  vi.spyOn(Storage.prototype, method).mockImplementation(() => {
    throw new DOMException("Site data is blocked", "SecurityError");
  });
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("useLicenseBannerDismissal", () => {
  test("is not dismissed until the user dismisses the banner", async () => {
    // GIVEN
    const license = EXPIRING;

    // WHEN
    const { result } = await renderHook(() => useLicenseBannerDismissal(license));

    // THEN
    expect(result.current.isDismissed).toBe(false);
  });

  test("hides the banner as soon as it is dismissed", async () => {
    // GIVEN
    const hook = await renderHook(() => useLicenseBannerDismissal(EXPIRING));

    // WHEN
    await hook.act(() => {
      hook.result.current.dismiss();
    });

    // THEN
    expect(hook.result.current.isDismissed).toBe(true);
  });

  test.each([
    { name: "a license", license: EXPIRING },
    { name: "no license ID", license: UNLICENSED },
  ])(
    "remembers the dismissal in the browser session for $name in the same state",
    async ({ license }) => {
      // GIVEN
      await dismissFor(license);

      // WHEN
      const { result } = await renderHook(() => useLicenseBannerDismissal(license));

      // THEN
      expect(result.current.isDismissed).toBe(true);
      expect(sessionStorage.length).toBe(1);
    }
  );

  test("shows the banner again for a different license", async () => {
    // GIVEN
    await dismissFor(EXPIRING);
    const renewed = generateLicenseInfo({
      state: "expiring",
      license_id: "0b6c2e9d-1a4f-4d8e-b3c7-5e2f1a9d8c70",
    });

    // WHEN
    const { result } = await renderHook(() => useLicenseBannerDismissal(renewed));

    // THEN
    expect(result.current.isDismissed).toBe(false);
  });

  test("shows the banner again when the state of the license changes", async () => {
    // GIVEN
    const hook = await renderHook<LicenseInfo, ReturnType<typeof useLicenseBannerDismissal>>(
      (license = EXPIRING) => useLicenseBannerDismissal(license),
      { initialProps: EXPIRING }
    );
    await hook.act(() => {
      hook.result.current.dismiss();
    });

    // WHEN
    await hook.rerender({ ...EXPIRING, state: "expired" });

    // THEN
    expect(hook.result.current.isDismissed).toBe(false);
  });

  test("falls back to not dismissed when the session storage cannot be read", async () => {
    // GIVEN
    blockSessionStorage("getItem");

    // WHEN
    const { result } = await renderHook(() => useLicenseBannerDismissal(EXPIRING));

    // THEN
    expect(result.current.isDismissed).toBe(false);
  });

  test("keeps a dismissal the session storage rejects while the banner stays mounted", async () => {
    // GIVEN
    blockSessionStorage("setItem");
    const hook = await renderHook(() => useLicenseBannerDismissal(EXPIRING));

    // WHEN
    await hook.act(() => {
      hook.result.current.dismiss();
    });

    // THEN
    expect(hook.result.current.isDismissed).toBe(true);
  });
});
