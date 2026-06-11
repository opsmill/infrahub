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

  test("sends an id-less lazy payload targeting the account with both values", async () => {
    await upsertUserPreferenceFromApi({
      accountId: "account-1",
      dateFormat: "dd/MM/yyyy",
      timezone: "Europe/Paris",
    });

    expect(graphqlClient.mutate).toHaveBeenCalledTimes(1);
    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables).toEqual({
      data: {
        account: { id: "account-1" },
        date_format: { value: "dd/MM/yyyy" },
        timezone: { value: "Europe/Paris" },
      },
    });
    expect(variables?.data).not.toHaveProperty("id");
  });

  test("sends explicit null values to clear an override", async () => {
    await upsertUserPreferenceFromApi({
      accountId: "account-1",
      dateFormat: null,
      timezone: "UTC",
    });

    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables?.data).toEqual({
      account: { id: "account-1" },
      date_format: { value: null },
      timezone: { value: "UTC" },
    });
  });
});
