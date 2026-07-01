import { beforeEach, describe, expect, test, vi } from "vitest";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { upsertUserPreferenceFromApi } from "@/entities/preferences/api/upsert-user-preference-from-api";

vi.mock("@/shared/api/graphql/graphqlClientApollo", () => ({
  default: {
    query: vi.fn().mockResolvedValue({ data: {} }),
    mutate: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

describe("upsertUserPreferenceFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("sends date_format and timezone with no account argument", async () => {
    await upsertUserPreferenceFromApi({
      dateFormat: "EU_DATETIME",
      timezone: "Europe/Paris",
    });

    expect(graphqlClient.mutate).toHaveBeenCalledTimes(1);
    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables).toEqual({
      dateFormat: "EU_DATETIME",
      timezone: "Europe/Paris",
    });
    expect(variables).not.toHaveProperty("account");
    expect(variables).not.toHaveProperty("id");
  });

  test("sends explicit null to reset a field to the global default", async () => {
    await upsertUserPreferenceFromApi({
      dateFormat: null,
      timezone: "UTC",
    });

    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables).toEqual({
      dateFormat: null,
      timezone: "UTC",
    });
  });

  test("omits a field that is not provided so it is left unchanged", async () => {
    await upsertUserPreferenceFromApi({ timezone: "UTC" });

    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables).toEqual({ timezone: "UTC" });
    expect(variables).not.toHaveProperty("dateFormat");
  });
});
