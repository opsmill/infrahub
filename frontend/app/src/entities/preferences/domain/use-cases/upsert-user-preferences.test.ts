import { beforeEach, describe, expect, test, vi } from "vitest";

import { upsertUserPreferencesFromApi } from "@/entities/preferences/api/upsert-user-preferences-from-api";
import { upsertUserPreferences } from "@/entities/preferences/domain/use-cases/upsert-user-preferences";

vi.mock("@/entities/preferences/api/upsert-user-preferences-from-api");

type UpsertResult = Awaited<ReturnType<typeof upsertUserPreferencesFromApi>>;

function mockOk(ok: boolean) {
  vi.mocked(upsertUserPreferencesFromApi).mockResolvedValue({
    data: { InfrahubSetPreferences: { ok, date_format: null, timezone: null } },
  } as unknown as UpsertResult);
}

describe("upsertUserPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOk(true);
  });

  test("sends date_format and timezone as variables", async () => {
    await upsertUserPreferences({ dateFormat: "EU_DATETIME", timezone: "Europe/Paris" });

    expect(upsertUserPreferencesFromApi).toHaveBeenCalledWith({
      dateFormat: "EU_DATETIME",
      timezone: "Europe/Paris",
    });
  });

  test("sends explicit null to reset a field to the global default", async () => {
    await upsertUserPreferences({ dateFormat: null, timezone: "UTC" });

    expect(upsertUserPreferencesFromApi).toHaveBeenCalledWith({
      dateFormat: null,
      timezone: "UTC",
    });
  });

  test("omits a field that is not provided so it is left unchanged", async () => {
    await upsertUserPreferences({ timezone: "UTC" });

    const variables = vi.mocked(upsertUserPreferencesFromApi).mock.calls[0]?.[0];
    expect(variables).toEqual({ timezone: "UTC" });
    expect(variables).not.toHaveProperty("dateFormat");
  });

  test("throws the failure message when the mutation reports ok: false", async () => {
    mockOk(false);

    await expect(upsertUserPreferences({ timezone: "UTC" })).rejects.toThrow(
      "Failed to save your preferences"
    );
  });
});
