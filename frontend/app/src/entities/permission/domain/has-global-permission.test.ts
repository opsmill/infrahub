import { beforeEach, describe, expect, test, vi } from "vitest";

import { getGlobalPermissionsFromApi } from "@/entities/permission/api/get-global-permissions-from-api";
import { hasGlobalPermission } from "@/entities/permission/domain/has-global-permission";

vi.mock("@/entities/permission/api/get-global-permissions-from-api");

type GlobalPermissionsResult = Awaited<ReturnType<typeof getGlobalPermissionsFromApi>>;

function mockEdges(edges: Array<{ action: string; decision: string }>) {
  // Only the shape the domain reads matters here; cast the partial stub through
  // unknown to the full ApolloQueryResult the api returns.
  vi.mocked(getGlobalPermissionsFromApi).mockResolvedValue({
    data: {
      InfrahubPermissions: {
        global_permissions: { edges: edges.map((node) => ({ node })) },
      },
    },
  } as unknown as GlobalPermissionsResult);
}

describe("hasGlobalPermission", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns true when the action is present with an ALLOW decision", async () => {
    mockEdges([{ action: "manage_global_preferences", decision: "ALLOW" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
  });

  test("treats branch-relative ALLOW_* decisions as granted", async () => {
    mockEdges([{ action: "manage_global_preferences", decision: "ALLOW_DEFAULT" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
  });

  test("returns false when the action is present but denied", async () => {
    mockEdges([{ action: "manage_global_preferences", decision: "DENY" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("returns false when the action is absent", async () => {
    mockEdges([{ action: "some_other_permission", decision: "ALLOW" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("returns false when there are no global permissions at all", async () => {
    mockEdges([]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("a super_admin grant satisfies any action (mirrors the backend bypass)", async () => {
    mockEdges([{ action: "super_admin", decision: "ALLOW" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
  });
});
