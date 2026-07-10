import { beforeEach, describe, expect, test, vi } from "vitest";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { updateGlobalPreferenceFromApi } from "@/entities/preferences/api/update-global-preference-from-api";

vi.mock("@/shared/api/graphql/graphqlClientApollo", () => ({
  default: {
    query: vi.fn().mockResolvedValue({ data: {} }),
    mutate: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

const OK_RESULT = {
  data: { InfrahubSetPreferences: { ok: true, date_format: null, timezone: null } },
};

describe("updateGlobalPreferenceFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(graphqlClient.mutate).mockResolvedValue(OK_RESULT as never);
  });

  test("sends date_format and timezone with no id argument", async () => {
    await updateGlobalPreferenceFromApi({ dateFormat: "EU_DATETIME", timezone: "Europe/Paris" });

    expect(graphqlClient.mutate).toHaveBeenCalledTimes(1);
    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables).toEqual({ dateFormat: "EU_DATETIME", timezone: "Europe/Paris" });
    expect(variables).not.toHaveProperty("id");
  });

  test("sends explicit null to clear the org default", async () => {
    await updateGlobalPreferenceFromApi({ dateFormat: null, timezone: "UTC" });

    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables).toEqual({ dateFormat: null, timezone: "UTC" });
  });

  test("omits a field that is not provided so it is left unchanged", async () => {
    await updateGlobalPreferenceFromApi({ timezone: "UTC" });

    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables).toEqual({ timezone: "UTC" });
    expect(variables).not.toHaveProperty("dateFormat");
  });

  test("throws when the mutation reports ok: false (application-level failure)", async () => {
    // ok: false means the update did not happen, even though Apollo resolved without errors.
    vi.mocked(graphqlClient.mutate).mockResolvedValue({
      data: { InfrahubSetPreferences: { ok: false, date_format: null, timezone: null } },
    } as never);

    await expect(updateGlobalPreferenceFromApi({ timezone: "UTC" })).rejects.toThrow();
  });
});
