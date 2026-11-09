import type React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  DatePreferencesContext,
  type ResolvedDatePreferences,
} from "@/shared/context/date-preferences-context";

import { type FieldSchema, ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/object/domain/model/node";

import { render } from "../../../tests/components/render";

// Fixed "now" so any age-based rendering heuristic is deterministic.
const FIXED_INSTANT = new Date("2026-06-11T14:30:00Z");

const TOKYO_PREFS: ResolvedDatePreferences = {
  pattern: "yyyy-MM-dd HH:mm:ss",
  timezone: "Asia/Tokyo",
};

const dateTimeSchema = { name: "expiration", kind: "DateTime" } as FieldSchema;

function attributeValue(value: string): NodeAttributeWithMetadata {
  return { value } as NodeAttributeWithMetadata;
}

function withPrefs(node: React.ReactElement) {
  return <DatePreferencesContext value={TOKYO_PREFS}>{node}</DatePreferencesContext>;
}

describe("ObjectAttributeValue", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(FIXED_INSTANT);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("DateTime attribute renders the full preferred datetime, even months in the past", async () => {
    // 09:30 UTC is 18:30 in Tokyo.
    const component = await render(
      withPrefs(
        <ObjectAttributeValue
          attributeSchema={dateTimeSchema}
          attributeData={attributeValue("2026-01-15T09:30:00Z")}
        />
      )
    );

    await expect.element(component.getByText("2026-01-15 18:30:00")).toBeVisible();
  });

  test("DateTime attribute renders the full preferred datetime for recent values too", async () => {
    const component = await render(
      withPrefs(
        <ObjectAttributeValue
          attributeSchema={dateTimeSchema}
          attributeData={attributeValue("2026-06-09T14:30:00Z")}
        />
      )
    );

    await expect.element(component.getByText("2026-06-09 23:30:00")).toBeVisible();
  });
});
