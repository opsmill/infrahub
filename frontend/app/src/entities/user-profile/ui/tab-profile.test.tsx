import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";
import { getEffectivePreferences } from "@/entities/preferences/domain/use-cases/get-effective-preferences";
import { upsertMyUserPreference } from "@/entities/preferences/domain/use-cases/upsert-my-user-preference";

import { render } from "../../../../tests/components/render";
import TabProfile from "./tab-profile";

// Stub the account-detail cards (their schema/query machinery is out of scope here); we only assert
// the profile tab composes the account details with the user-preferences card in the main column.
vi.mock("@/entities/nodes/object/ui/object-details/object-details-card", () => ({
  ObjectDetailsCard: () => <div data-testid="object-details-card">account details</div>,
}));
vi.mock("@/entities/nodes/object/ui/object-details/object-profiles-groups-card", () => ({
  ObjectProfilesGroupsCard: () => null,
}));
vi.mock("@/entities/nodes/object/ui/object-details/object-activities-card", () => ({
  ObjectActivitiesCard: () => null,
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
vi.mock("@/entities/preferences/domain/use-cases/get-effective-preferences");
vi.mock("@/entities/preferences/domain/use-cases/upsert-my-user-preference");

const baseEffective: EffectivePreferences = {
  dateFormat: { value: "EU_DATETIME", source: "GLOBAL" },
  timezone: { value: "Europe/Paris", source: "GLOBAL" },
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

  test("composes the account details with the user-preferences card in the main column", async () => {
    const component = await render(<TabProfile />);

    const details = component.getByTestId("object-details-card");
    await expect.element(details).toBeVisible();

    const preferencesTitle = component.getByText("Preferences");
    await expect.element(preferencesTitle).toBeVisible();
    await expect.element(component.getByRole("combobox", { name: /date format/i })).toBeVisible();
    await expect.element(component.getByRole("combobox", { name: /timezone/i })).toBeVisible();

    // The preferences card comes after the account details in the main column.
    const ordered = Array.from(component.container.querySelectorAll<HTMLElement>("*"));
    const detailsIndex = ordered.indexOf(details.element() as HTMLElement);
    const titleIndex = ordered.indexOf(preferencesTitle.element() as HTMLElement);
    expect(detailsIndex).toBeGreaterThanOrEqual(0);
    expect(titleIndex).toBeGreaterThan(detailsIndex);
  });
});
