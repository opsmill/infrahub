import { useState } from "react";

import type { LicenseInfo } from "@/entities/license/domain/model/license";

const DISMISSED = "dismissed";

type DismissalScope = Pick<LicenseInfo, "license_id" | "state" | "reason">;

function storageKey({ license_id, state, reason }: DismissalScope): string {
  return `infrahub.license.banner-dismissed.${license_id ?? "none"}.${state}.${reason ?? "none"}`;
}

function readDismissed(key: string): boolean {
  try {
    return sessionStorage.getItem(key) === DISMISSED;
  } catch {
    // Storage throws when the user blocks site data, and an unreadable dismissal must not hide the banner.
    return false;
  }
}

function writeDismissed(key: string): void {
  try {
    sessionStorage.setItem(key, DISMISSED);
  } catch {
    // Blocked site data or a full quota: the dismissal holds only while the banner stays mounted.
  }
}

/** Remembers for the browser session that the banner was dismissed for this license ID, state and failure reason. */
export function useLicenseBannerDismissal(license: DismissalScope) {
  const key = storageKey(license);
  const [dismissedKey, setDismissedKey] = useState<string | null>(null);

  const dismiss = () => {
    writeDismissed(key);
    setDismissedKey(key);
  };

  return { isDismissed: dismissedKey === key || readDismissed(key), dismiss };
}
