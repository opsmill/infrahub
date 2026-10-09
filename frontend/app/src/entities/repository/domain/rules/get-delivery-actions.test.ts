import { describe, expect, it } from "vitest";

import { getDeliveryActions } from "@/entities/repository/domain/rules/get-delivery-actions";

describe("getDeliveryActions", () => {
  it("refuses retry and abandon when nothing is pending", () => {
    // GIVEN
    const status = "none";

    // WHEN
    const actions = getDeliveryActions(status);

    // THEN
    expect(actions).toEqual({ canRetry: false, canAbandon: false });
  });

  it.each(["pending", "action-required"] as const)("allows retry and abandon when %s", (status) => {
    // GIVEN
    const pendingStatus = status;

    // WHEN
    const actions = getDeliveryActions(pendingStatus);

    // THEN
    expect(actions).toEqual({ canRetry: true, canAbandon: true });
  });
});
