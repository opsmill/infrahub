export const SCHEDULED_FLOW_HEALTH_OVERDUE = "OVERDUE" as const;
export const SCHEDULED_FLOW_HEALTH_FAILED = "FAILED" as const;
export const SCHEDULED_FLOW_HEALTH_CANCELLED = "CANCELLED" as const;
export const SCHEDULED_FLOW_HEALTH_NO_RECENT_RUNS = "NO_RECENT_RUNS" as const;
export const SCHEDULED_FLOW_HEALTH_NEVER_RUN = "NEVER_RUN" as const;
export const SCHEDULED_FLOW_HEALTH_PAUSED = "PAUSED" as const;
export const SCHEDULED_FLOW_HEALTH_HEALTHY = "HEALTHY" as const;

export const SCHEDULED_FLOW_HEALTHS = [
  SCHEDULED_FLOW_HEALTH_OVERDUE,
  SCHEDULED_FLOW_HEALTH_FAILED,
  SCHEDULED_FLOW_HEALTH_CANCELLED,
  SCHEDULED_FLOW_HEALTH_NO_RECENT_RUNS,
  SCHEDULED_FLOW_HEALTH_NEVER_RUN,
  SCHEDULED_FLOW_HEALTH_PAUSED,
  SCHEDULED_FLOW_HEALTH_HEALTHY,
] as const;

export type ScheduledFlowHealth = (typeof SCHEDULED_FLOW_HEALTHS)[number];

export const SCHEDULED_FLOW_HEALTH_LABELS: Record<ScheduledFlowHealth, string> = {
  [SCHEDULED_FLOW_HEALTH_OVERDUE]: "Overdue",
  [SCHEDULED_FLOW_HEALTH_FAILED]: "Failed",
  [SCHEDULED_FLOW_HEALTH_CANCELLED]: "Cancelled",
  [SCHEDULED_FLOW_HEALTH_NO_RECENT_RUNS]: "No recent runs",
  [SCHEDULED_FLOW_HEALTH_NEVER_RUN]: "Never run",
  [SCHEDULED_FLOW_HEALTH_PAUSED]: "Paused",
  [SCHEDULED_FLOW_HEALTH_HEALTHY]: "Healthy",
};

export const SCHEDULED_FLOW_HEALTH_DESCRIPTIONS: Record<ScheduledFlowHealth, string> = {
  [SCHEDULED_FLOW_HEALTH_OVERDUE]:
    "No run has executed within three of this flow's scheduled intervals.",
  [SCHEDULED_FLOW_HEALTH_FAILED]: "The most recent run that executed failed or crashed.",
  [SCHEDULED_FLOW_HEALTH_CANCELLED]:
    "The most recent run that executed was cancelled, often by a concurrency collision.",
  [SCHEDULED_FLOW_HEALTH_NO_RECENT_RUNS]:
    "No run history is available and it cannot be told apart from purged history.",
  [SCHEDULED_FLOW_HEALTH_NEVER_RUN]: "This flow has not run since it was registered.",
  [SCHEDULED_FLOW_HEALTH_PAUSED]: "The schedule is switched off, so no run is expected.",
  [SCHEDULED_FLOW_HEALTH_HEALTHY]:
    "The most recent run that executed neither failed nor was cancelled.",
};

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const SECONDS_PER_DAY = 86_400;

interface ScheduleSentenceInput {
  cron: string;
  intervalSeconds?: number | null;
  nextRunAt?: string | null;
  timezone?: string | null;
}

/**
 * Read an instant as a wall clock in the given zone, so the time and the zone it is labelled with
 * agree. An unrecognised zone falls back to UTC, which is what the reading is then labelled.
 */
function getWallClock(
  date: Date,
  timeZone: string
): { hours: string; minutes: string; zone: string } {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(date);
    const hours = parts.find(({ type }) => type === "hour")?.value;
    const minutes = parts.find(({ type }) => type === "minute")?.value;

    if (hours && minutes) return { hours, minutes, zone: timeZone };
  } catch {
    // Intl throws on an unknown IANA zone.
  }

  return {
    hours: String(date.getUTCHours()).padStart(2, "0"),
    minutes: String(date.getUTCMinutes()).padStart(2, "0"),
    zone: "UTC",
  };
}

/**
 * Render a cron schedule as a sentence, falling back to the raw expression when the shape is
 * not one the helper recognises.
 */
export function getScheduleSentence({
  cron,
  intervalSeconds,
  nextRunAt,
  timezone,
}: ScheduleSentenceInput): string {
  if (!intervalSeconds || intervalSeconds <= 0) return cron;

  if (intervalSeconds === SECONDS_PER_MINUTE) return "Every minute";

  if (intervalSeconds < SECONDS_PER_HOUR && intervalSeconds % SECONDS_PER_MINUTE === 0) {
    return `Every ${intervalSeconds / SECONDS_PER_MINUTE} minutes`;
  }

  const nextRun = nextRunAt ? new Date(nextRunAt) : null;
  if (!nextRun || Number.isNaN(nextRun.getTime())) return cron;

  const { hours, minutes, zone } = getWallClock(nextRun, timezone ?? "UTC");

  if (intervalSeconds === SECONDS_PER_HOUR) return `Hourly at :${minutes}`;
  if (intervalSeconds === SECONDS_PER_DAY) return `Daily at ${hours}:${minutes} ${zone}`;

  return cron;
}
