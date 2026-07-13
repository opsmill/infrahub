import { beforeEach, describe, expect, test, vi } from "vitest";

import { upsertUserPreferenceFromApi } from "@/entities/preferences/api/upsert-user-preference-from-api";
import { upsertMyUserPreference } from "@/entities/preferences/domain/use-cases/upsert-my-user-preference";

vi.mock("@/entities/preferences/api/upsert-user-preference-from-api");

type UpsertResult = Awaited<ReturnType<typeof upsertUserPreferenceFromApi>>;

function mockOk(ok: boolean) {
  vi.mocked(upsertUserPreferenceFromApi).mockResolvedValue({
    data: { InfrahubSetPreferences: { ok, date_format: null, timezone: null } },
  } as unknown as UpsertResult);
}

describe("upsertMyUserPreference", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOk(true);
  });

  test("sends date_format and timezone as variables", async () => {
    await upsertMyUserPreference({ dateFormat: "EU_DATETIME", timezone: "Europe/Paris" });

    expect(upsertUserPreferenceFromApi).toHaveBeenCalledWith({
      dateFormat: "EU_DATETIME",
      timezone: "Europe/Paris",
    });
  });

  test("sends explicit null to reset a field to the global default", async () => {
    await upsertMyUserPreference({ dateFormat: null, timezone: "UTC" });

    expect(upsertUserPreferenceFromApi).toHaveBeenCalledWith({ dateFormat: null, timezone: "UTC" });
  });

  test("omits a field that is not provided so it is left unchanged", async () => {
    await upsertMyUserPreference({ timezone: "UTC" });

    const variables = vi.mocked(upsertUserPreferenceFromApi).mock.calls[0]?.[0];
    expect(variables).toEqual({ timezone: "UTC" });
    expect(variables).not.toHaveProperty("dateFormat");
  });

  test("throws the failure message when the mutation reports ok: false", async () => {
    mockOk(false);

    await expect(upsertMyUserPreference({ timezone: "UTC" })).rejects.toThrow(
      "Failed to save your preferences"
    );
  });
});
