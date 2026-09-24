import { describe, expect, test } from "vitest";

import {
  SCHEDULED_FLOW_HEALTH_CANCELLED,
  SCHEDULED_FLOW_HEALTH_FAILED,
  SCHEDULED_FLOW_HEALTH_LABELS,
  SCHEDULED_FLOW_HEALTHS,
} from "@/entities/scheduled-flows/domain/model/scheduled-flow";

import { render } from "../../../../tests/components/render";
import { ScheduledFlowHealthBadge } from "./scheduled-flow-health-badge";

describe("ScheduledFlowHealthBadge", () => {
  test.each(SCHEDULED_FLOW_HEALTHS)(
    "locates the %s verdict by its text, not its colour",
    async (health) => {
      // GIVEN
      const label = SCHEDULED_FLOW_HEALTH_LABELS[health];

      // WHEN
      const component = await render(<ScheduledFlowHealthBadge health={health} />);

      // THEN
      await expect.element(component.getByText(label, { exact: true })).toBeVisible();
    }
  );

  test("distinguishes a failed flow from a cancelled one by word", async () => {
    // GIVEN
    const failed = await render(<ScheduledFlowHealthBadge health={SCHEDULED_FLOW_HEALTH_FAILED} />);

    // WHEN
    const cancelled = await render(
      <ScheduledFlowHealthBadge health={SCHEDULED_FLOW_HEALTH_CANCELLED} />
    );

    // THEN
    await expect.element(failed.getByText("Failed", { exact: true })).toBeVisible();
    await expect.element(cancelled.getByText("Cancelled", { exact: true })).toBeVisible();
  });
});
