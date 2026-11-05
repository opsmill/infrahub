import { beforeEach, describe, expect, test, vi } from "vitest";

import { updateGlobalPreferenceFromApi } from "@/entities/preferences/api/update-global-preference-from-api";
import { updateGlobalPreference } from "@/entities/preferences/domain/use-cases/update-global-preference";

vi.mock("@/entities/preferences/api/update-global-preference-from-api");

type UpdateResult = Awaited<ReturnType<typeof updateGlobalPreferenceFromApi>>;

function mockOk(ok: boolean) {
  vi.mocked(updateGlobalPreferenceFromApi).mockResolvedValue({
    data: {
      InfrahubSetPreferences: {
        ok,
        date_format: null,
        timezone: null,
        instance_label: null,
        instance_color: null,
      },
    },
  } as unknown as UpdateResult);
}

describe("updateGlobalPreference", () => {
  beforeEach(() => {
    mockOk(true);
  });

  test("sends date_format and timezone as variables", async () => {
    await updateGlobalPreference({ dateFormat: "EU_DATETIME", timezone: "Europe/Paris" });

    expect(updateGlobalPreferenceFromApi).toHaveBeenCalledWith({
      dateFormat: "EU_DATETIME",
      timezone: "Europe/Paris",
    });
  });

  test("sends explicit null to clear a field", async () => {
    await updateGlobalPreference({ dateFormat: null, timezone: "UTC" });

    expect(updateGlobalPreferenceFromApi).toHaveBeenCalledWith({
      dateFormat: null,
      timezone: "UTC",
    });
  });

  test("omits a field that is not provided so it is left unchanged", async () => {
    await updateGlobalPreference({ timezone: "UTC" });

    const variables = vi.mocked(updateGlobalPreferenceFromApi).mock.calls[0]?.[0];
    expect(variables).toEqual({ timezone: "UTC" });
    expect(variables).not.toHaveProperty("dateFormat");
  });

  test("sends the instance label and color as variables", async () => {
    // GIVEN
    const params = { instanceLabel: "QA", instanceColor: "RED" as const };

    // WHEN
    await updateGlobalPreference(params);

    // THEN
    expect(updateGlobalPreferenceFromApi).toHaveBeenCalledWith({
      instanceLabel: "QA",
      instanceColor: "RED",
    });
  });

  test("omits the instance label and color when they are not provided", async () => {
    // GIVEN
    const params = { timezone: "UTC" };

    // WHEN
    await updateGlobalPreference(params);

    // THEN
    const variables = vi.mocked(updateGlobalPreferenceFromApi).mock.calls[0]?.[0];
    expect(variables).not.toHaveProperty("instanceLabel");
    expect(variables).not.toHaveProperty("instanceColor");
  });

  test("sends explicit null to reset the instance label and color", async () => {
    // GIVEN
    const params = { instanceLabel: null, instanceColor: null };

    // WHEN
    await updateGlobalPreference(params);

    // THEN
    expect(updateGlobalPreferenceFromApi).toHaveBeenCalledWith({
      instanceLabel: null,
      instanceColor: null,
    });
  });

  test("throws the failure message when the mutation reports ok: false", async () => {
    mockOk(false);

    await expect(updateGlobalPreference({ timezone: "UTC" })).rejects.toThrow(
      "Failed to update the global preferences"
    );
  });
});
