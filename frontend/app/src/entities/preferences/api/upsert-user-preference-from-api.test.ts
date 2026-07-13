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

  test("forwards the given variables to the USER-scope mutation", async () => {
    await upsertUserPreferenceFromApi({ dateFormat: "EU_DATETIME", timezone: "Europe/Paris" });

    expect(graphqlClient.mutate).toHaveBeenCalledTimes(1);
    const { variables } = vi.mocked(graphqlClient.mutate).mock.calls[0]?.[0] ?? {};
    expect(variables).toEqual({ dateFormat: "EU_DATETIME", timezone: "Europe/Paris" });
  });
});
