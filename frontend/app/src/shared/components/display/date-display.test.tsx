import type React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { DateDisplay } from "@/shared/components/display/date-display";
import {
  DatePreferencesContext,
  type ResolvedDatePreferences,
} from "@/shared/context/date-preferences-context";

import { render } from "../../../../tests/components/render";

// Fixed "now" so the relative/compact heuristic and "x ago" strings are deterministic.
const FIXED_INSTANT = new Date("2026-06-11T14:30:00Z");

const PARIS_PREFS: ResolvedDatePreferences = {
  pattern: "yyyy-MM-dd HH:mm",
  timezone: "Europe/Paris",
};

function withPrefs(node: React.ReactElement, prefs: ResolvedDatePreferences | null = PARIS_PREFS) {
  return prefs === null ? (
    node
  ) : (
    <DatePreferencesContext value={prefs}>{node}</DatePreferencesContext>
  );
}

describe("DateDisplay", () => {
  beforeEach(() => {
    // Fake ONLY Date (not timers) so the relative/compact heuristic is deterministic while
    // React Aria's tooltip open-delay still runs on real timers (matches user-preferences-card).
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(FIXED_INSTANT);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("relative branch: recent date shows 'x ago'", async () => {
    const twoDaysAgo = new Date("2026-06-09T14:30:00Z");
    const component = await render(withPrefs(<DateDisplay date={twoDaysAgo} />));
    await expect.element(component.getByText("2 days ago")).toBeVisible();
  });

  test("compact branch: old date renders the preferred date (honouring format + timezone)", async () => {
    // > 7 days old, so the compact branch fires. It must use the preferred date pattern in the
    // preferred zone — 2026-01-15 14:30 UTC is still 2026-01-15 in Paris — not a fixed browser-zone
    // "d MMM" string.
    const old = new Date("2026-01-15T14:30:00Z");
    const component = await render(withPrefs(<DateDisplay date={old} />));
    await expect.element(component.getByText("2026-01-15")).toBeVisible();
  });

  test("compact branch: falls back to the browser-locale date when no preference is set", async () => {
    const old = new Date("2026-01-15T14:30:00Z");
    const component = await render(
      withPrefs(<DateDisplay date={old} />, { pattern: null, timezone: null })
    );
    // No preferred pattern → locale medium date; not the old fixed "d MMM" and not a full datetime.
    await expect.element(component.getByText(/Jan.*2026|2026.*Jan|1\/15\/2026/)).toBeVisible();
  });

  test('variant="datetime" renders the preferred pattern + timezone inline', async () => {
    const component = await render(
      withPrefs(<DateDisplay date={FIXED_INSTANT} variant="datetime" />)
    );
    // Europe/Paris (UTC+2 in June) → 16:30.
    await expect.element(component.getByText("2026-06-11 16:30")).toBeVisible();
  });

  test("explicit dateFormat prop escape hatch overrides the heuristic", async () => {
    const component = await render(
      withPrefs(<DateDisplay date={FIXED_INSTANT} dateFormat="yyyy" />)
    );
    await expect.element(component.getByText("2026")).toBeVisible();
  });

  test("tooltip shows the preferred full datetime + timezone", async () => {
    const old = new Date("2026-01-15T09:30:00Z");
    const component = await render(withPrefs(<DateDisplay date={old} />));

    // Compact inline text (old date) is the trigger; the tooltip carries the full preferred
    // datetime. The trigger is a React Aria non-interactive (span) trigger — the browser harness
    // can't reliably emulate the pointer `useHover` needs, but focus opens the tooltip just as well.
    (component.getByText("2026-01-15").element() as HTMLElement).focus();

    // Paris wall clock for 2026-01-15 09:30 UTC (CET, UTC+1) is 10:30.
    await expect
      .element(component.getByRole("tooltip", { name: "2026-01-15 10:30" }))
      .toBeVisible();
  });

  test("no provider mounted: renders with browser-locale fallback (no crash)", async () => {
    const component = await render(
      withPrefs(<DateDisplay date={FIXED_INSTANT} variant="datetime" />, null)
    );
    // The compact/relative heuristic is bypassed; some non-empty datetime string renders.
    await expect.element(component.getByText(/2026/)).toBeVisible();
  });
});
