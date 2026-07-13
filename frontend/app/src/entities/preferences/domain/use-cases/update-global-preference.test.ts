import { beforeEach, describe, expect, test, vi } from "vitest";

import { updateGlobalPreferenceFromApi } from "@/entities/preferences/api/update-global-preference-from-api";
import { updateGlobalPreference } from "@/entities/preferences/domain/use-cases/update-global-preference";

vi.mock("@/entities/preferences/api/update-global-preference-from-api");

type UpdateResult = Awaited<ReturnType<typeof updateGlobalPreferenceFromApi>>;

function mockOk(ok: boolean) {
  vi.mocked(updateGlobalPreferenceFromApi).mockResolvedValue({
    data: { InfrahubSetPreferences: { ok, date_format: null, timezone: null } },
  } as unknown as UpdateResult);
}

describe("updateGlobalPreference", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

  test("throws the failure message when the mutation reports ok: false", async () => {
    mockOk(false);

    await expect(updateGlobalPreference({ timezone: "UTC" })).rejects.toThrow(
      "Failed to update the global preferences"
    );
  });
});
