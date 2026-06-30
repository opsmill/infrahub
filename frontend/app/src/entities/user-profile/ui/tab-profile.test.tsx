import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getEffectivePreferences } from "@/entities/preferences/domain/get-effective-preferences";
import type { EffectivePreferences } from "@/entities/preferences/domain/types";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";

import { render } from "../../../../tests/components/render";
import TabProfile from "./tab-profile";

// The object-details subtree pulls in schema/query machinery that is out of scope
// here; we only assert that the profile tab composes <ObjectDetails/> above the
// user-preferences card, so stub the details with a sentinel.
vi.mock("@/entities/nodes/object/ui/object-details/object-details", () => ({
  ObjectDetails: () => <div data-testid="object-details">object details</div>,
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
  dateFormat: "dd/MM/yyyy",
  timezone: "Europe/Paris",
  userDateFormat: null,
  userTimezone: null,
  globalDateFormat: "dd/MM/yyyy",
  globalTimezone: "Europe/Paris",
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
