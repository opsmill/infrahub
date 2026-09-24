import { describe, expect, test } from "vitest";

import {
  getScheduleSentence,
  SCHEDULED_FLOW_HEALTH_LABELS,
  SCHEDULED_FLOW_HEALTHS,
} from "./scheduled-flow";

describe("getScheduleSentence", () => {
  test("renders an every-minute schedule", () => {
    // GIVEN
    const schedule = { cron: "* * * * *", intervalSeconds: 60 };

    // WHEN
    const sentence = getScheduleSentence(schedule);

    // THEN
    expect(sentence).toBe("Every minute");
  });

  test("renders a multi-minute schedule", () => {
    // GIVEN
    const schedule = { cron: "*/5 * * * *", intervalSeconds: 300 };

    // WHEN
    const sentence = getScheduleSentence(schedule);

    // THEN
    expect(sentence).toBe("Every 5 minutes");
  });

  test("renders an hourly schedule with its minute", () => {
    // GIVEN
    const schedule = {
      cron: "17 * * * *",
      intervalSeconds: 3600,
      nextRunAt: "2026-09-24T08:17:00+00:00",
    };

    // WHEN
    const sentence = getScheduleSentence(schedule);

    // THEN
    expect(sentence).toBe("Hourly at :17");
  });

  test("renders the 02:00 daily telemetry schedule", () => {
    // GIVEN
    const schedule = {
      cron: "17 2 * * *",
      intervalSeconds: 86_400,
      nextRunAt: "2026-09-25T02:17:00+00:00",
    };

    // WHEN
    const sentence = getScheduleSentence(schedule);

    // THEN
    expect(sentence).toBe("Daily at 02:17 UTC");
  });

  test("renders the 03:00 daily webhook schedule", () => {
    // GIVEN
    const schedule = {
      cron: "42 3 * * *",
      intervalSeconds: 86_400,
      nextRunAt: "2026-09-25T03:42:00+00:00",
    };

    // WHEN
    const sentence = getScheduleSentence(schedule);

    // THEN
    expect(sentence).toBe("Daily at 03:42 UTC");
  });

  test("falls back to the raw cron for a shape it does not recognise", () => {
    // GIVEN
    const schedule = {
      cron: "0 0 1 */3 *",
      intervalSeconds: 7_862_400,
      nextRunAt: "2026-10-01T00:00:00+00:00",
    };

    // WHEN
    const sentence = getScheduleSentence(schedule);

    // THEN
    expect(sentence).toBe("0 0 1 */3 *");
  });

  test("falls back to the raw cron when the interval could not be derived", () => {
    // GIVEN
    const schedule = { cron: "not a cron", intervalSeconds: null };

    // WHEN
    const sentence = getScheduleSentence(schedule);

    // THEN
    expect(sentence).toBe("not a cron");
  });
});

describe("SCHEDULED_FLOW_HEALTH_LABELS", () => {
  test("gives every verdict a distinct human-readable label", () => {
    // GIVEN
    const healths = SCHEDULED_FLOW_HEALTHS;

    // WHEN
    const labels = healths.map((health) => SCHEDULED_FLOW_HEALTH_LABELS[health]);

    // THEN
    expect(labels).toEqual([
      "Overdue",
      "Failed",
      "Cancelled",
      "No recent runs",
      "Never run",
      "Paused",
      "Healthy",
    ]);
    expect(new Set(labels).size).toBe(healths.length);
  });
});
