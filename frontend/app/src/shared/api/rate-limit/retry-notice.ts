import React from "react";
import { toast } from "react-toastify";

import type { RetryOutcome } from "@/shared/api/rate-limit/policy";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

// One id, so a page load's worth of shed requests shares a single notice that
// follows the latest wait instead of stacking one per request.
const RETRY_TOAST_ID = "alert-shed-retry";

// Below this a replay is over before a person could read about it.
const NOTICE_THRESHOLD_MS = 1000;

// Once the last announced replay has fired, the notice stays up this long so a
// replay that is shed again can update it instead of flashing a new one.
const NOTICE_GRACE_MS = 500;

// Replays the notice has announced that have neither fired nor been abandoned.
let pendingReplays = 0;

function retryNoticeMessage(delayMs: number): string {
  const seconds = Math.ceil(delayMs / 1000);
  const unit = seconds === 1 ? "second" : "seconds";
  return `Infrahub is busy. Your request will be retried automatically in ${seconds} ${unit}.`;
}

function showNotice(delayMs: number): void {
  const render = React.createElement(Alert, {
    type: ALERT_TYPES.INFO,
    message: retryNoticeMessage(delayMs),
  });
  if (toast.isActive(RETRY_TOAST_ID)) {
    toast.update(RETRY_TOAST_ID, { render });
    return;
  }
  toast(render, { toastId: RETRY_TOAST_ID, autoClose: false });
}

function dismissIfIdle(): void {
  if (pendingReplays === 0) toast.dismiss(RETRY_TOAST_ID);
}

/**
 * Tells the person that a shed request is waiting, and for how long, when the
 * wait is long enough to notice.
 *
 * The returned callback must be told how the wait ended. The notice closes
 * once no announced replay is pending: shortly after the last one fires, or at
 * once when the last one is abandoned, so it never promises a replay that will
 * not happen.
 */
export function notifyRetryScheduled(delayMs: number): (outcome: RetryOutcome) => void {
  if (delayMs < NOTICE_THRESHOLD_MS) return () => undefined;

  pendingReplays += 1;
  showNotice(delayMs);

  let settled = false;
  return (outcome) => {
    if (settled) return;
    settled = true;
    pendingReplays -= 1;
    if (outcome === "abandoned") {
      dismissIfIdle();
      return;
    }
    setTimeout(dismissIfIdle, NOTICE_GRACE_MS);
  };
}
