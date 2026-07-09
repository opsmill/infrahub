import { beforeEach, describe, expect, test, vi } from "vitest";

import { getGlobalPermissionsFromApi } from "@/entities/permission/api/get-global-permissions-from-api";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";

vi.mock("@/entities/permission/api/get-global-permissions-from-api");

type GlobalPermissionsResult = Awaited<ReturnType<typeof getGlobalPermissionsFromApi>>;

function mockEdges(edges: Array<{ action: string; decision: string }>) {
  // Only the shape the domain reads matters; cast the partial stub to the full result type.
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

  // decision is the stringified PermissionDecision int: DENY=1, ALLOW_DEFAULT=2, ALLOW_OTHER=4, ALLOW_ALL=6.
  test("returns true when the action is present with ALLOW_ALL (6)", async () => {
    mockEdges([{ action: "manage_global_preferences", decision: "6" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
  });

  test("treats ALLOW_DEFAULT (2) / ALLOW_OTHER (4) as granted", async () => {
    mockEdges([{ action: "manage_global_preferences", decision: "2" }]);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);

    mockEdges([{ action: "manage_global_preferences", decision: "4" }]);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
  });

  test("returns false when the action is present but denied (1)", async () => {
    mockEdges([{ action: "manage_global_preferences", decision: "1" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("returns false when the action is absent", async () => {
    mockEdges([{ action: "some_other_permission", decision: "6" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("returns false when there are no global permissions at all", async () => {
    mockEdges([]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("a super_admin grant satisfies any action (mirrors the backend bypass)", async () => {
    mockEdges([{ action: "super_admin", decision: "6" }]);

    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
  });
});
