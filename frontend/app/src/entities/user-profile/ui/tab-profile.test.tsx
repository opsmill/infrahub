import type React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getEffectivePreferences } from "@/entities/preferences/domain/get-effective-preferences";
import type { EffectivePreferences } from "@/entities/preferences/domain/types";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";

import { render } from "../../../../tests/components/render";
import TabProfile from "./tab-profile";

// The object-details subtree pulls in schema/query machinery that is out of scope
// here; we only assert that the profile tab composes <ObjectDetails/> with the
// user-preferences card slotted into its left column. The stub mirrors the real
// component by rendering the details sentinel and then the leftColumnExtra slot
// (below it), so the composition under test is preserved.
vi.mock("@/entities/nodes/object/ui/object-details/object-details", () => ({
  ObjectDetails: ({ leftColumnExtra }: { leftColumnExtra?: React.ReactNode }) => (
    <div data-testid="object-details">
      <div>object details</div>
      {leftColumnExtra}
    </div>
  ),
}));

vi.mock("@/entities/schema/ui/hooks/useSchema", () => ({
  useSchema: () => ({ schema: { kind: "CoreGenericAccount" } }),
}));

vi.mock("@/entities/nodes/object/ui/queries/get-object.query", () => ({
  useGetObject: () => ({ data: { id: "1" }, error: null, isPending: false }),
}));

vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: () => ({ data: {}, error: null, isPending: false }),
}));

// The preferences card calls the same domain functions the old tab-preferences
// test mocked; the query hooks delegate to these.
vi.mock("@/entities/preferences/domain/get-effective-preferences");
vi.mock("@/entities/preferences/domain/upsert-my-user-preference");

const baseEffective: EffectivePreferences = {
  dateFormat: { value: "dd/MM/yyyy", source: "global" },
  timezone: { value: "Europe/Paris", source: "global" },
  global: { dateFormat: "dd/MM/yyyy", timezone: "Europe/Paris" },
  canEditGlobalPreferences: false,
};

describe("TabProfile", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-06-30T14:30:00"));
    vi.clearAllMocks();
    vi.mocked(getEffectivePreferences).mockResolvedValue(baseEffective);
    vi.mocked(upsertMyUserPreference).mockResolvedValue();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("renders the object details with the user-preferences card below it", async () => {
    const component = await render(<TabProfile />);

    const details = component.getByTestId("object-details");
    await expect.element(details).toBeVisible();

    // The user-preferences card renders below the details.
    const preferencesTitle = component.getByText("Preferences");
    await expect.element(preferencesTitle).toBeVisible();
    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();
    await expect.element(component.getByRole("combobox", { name: /timezone/i })).toBeVisible();

    // The preferences card comes after the details in document order.
    const ordered = Array.from(component.container.querySelectorAll<HTMLElement>("*"));
    const detailsIndex = ordered.indexOf(details.element() as HTMLElement);
    const titleIndex = ordered.indexOf(preferencesTitle.element() as HTMLElement);
    expect(detailsIndex).toBeGreaterThanOrEqual(0);
    expect(titleIndex).toBeGreaterThan(detailsIndex);
  });
});
