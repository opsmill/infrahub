import { beforeEach, describe, expect, test, vi } from "vitest";

import { getGlobalPermissionsFromApi } from "@/entities/permission/api/get-global-permissions-from-api";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";

vi.mock("@/entities/permission/api/get-global-permissions-from-api");

type GlobalPermissionsResult = Awaited<ReturnType<typeof getGlobalPermissionsFromApi>>;

// decision is the stringified int: DENY=1, ALLOW_DEFAULT=2, ALLOW_OTHER=4, ALLOW_ALL=6.
function mockEdges(edges: Array<[action: string, decision: string]>) {
  vi.mocked(getGlobalPermissionsFromApi).mockResolvedValue({
    data: {
      InfrahubPermissions: {
        global_permissions: {
          edges: edges.map(([action, decision]) => ({ node: { action, decision } })),
        },
      },
    },
  } as unknown as GlobalPermissionsResult);
}

function mockGlobalPermissions(globalPermissions: unknown) {
  vi.mocked(getGlobalPermissionsFromApi).mockResolvedValue({
    data: { InfrahubPermissions: { global_permissions: globalPermissions } },
  } as unknown as GlobalPermissionsResult);
}

describe("hasGlobalPermission", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("resolves true for any granting decision (2/4/6)", async () => {
    for (const decision of ["2", "4", "6"]) {
      mockEdges([["manage_global_preferences", decision]]);
      await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
    }
  });

  test("resolves false when the action is denied (1)", async () => {
    mockEdges([["manage_global_preferences", "1"]]);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("resolves false when the action is absent", async () => {
    mockEdges([["some_other_permission", "6"]]);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("a DENY for the action preempts an allow on the same action", async () => {
    mockEdges([
      ["manage_global_preferences", "6"],
      ["manage_global_preferences", "1"],
    ]);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("a super_admin grant satisfies any action", async () => {
    mockEdges([["super_admin", "6"]]);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
  });

  test("super_admin bypasses a DENY on the checked action", async () => {
    mockEdges([
      ["manage_global_preferences", "1"],
      ["super_admin", "6"],
    ]);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(true);
  });

  test("a denied super_admin grant is not a bypass", async () => {
    mockEdges([["super_admin", "1"]]);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });

  test("resolves false when global_permissions is null or undefined", async () => {
    mockGlobalPermissions(null);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);

    mockGlobalPermissions(undefined);
    await expect(hasGlobalPermission("manage_global_preferences")).resolves.toBe(false);
  });
});
