import { describe, expect, test } from "vitest";

import { BRANCH_STATUS } from "@/entities/branches/constants";

import { PERMISSION_ALLOW_ALL } from "./constants";
import type { PermissionData } from "./types";
import { getPermission } from "./utils";

const createPermissionNode = (overrides?: Partial<PermissionData>): { node: PermissionData } => ({
  node: {
    kind: "TestKind",
    view: "ALLOW",
    create: "ALLOW",
    update: "ALLOW",
    delete: "ALLOW",
    ...overrides,
  },
});

const awareSchema = { branch: "aware" } as { branch: string };
const agnosticSchema = { branch: "agnostic" } as { branch: string };
const localSchema = { branch: "local" } as { branch: string };

describe("getPermission", () => {
  describe("without branch options", () => {
    test("returns PERMISSION_ALLOW_ALL when no permission data", () => {
      const result = getPermission();

      expect(result).toEqual(PERMISSION_ALLOW_ALL);
    });

    test("returns PERMISSION_ALLOW_ALL when undefined", () => {
      const result = getPermission(undefined);

      expect(result).toEqual(PERMISSION_ALLOW_ALL);
    });

    test("returns allowed for all actions when all ALLOW", () => {
      const result = getPermission([createPermissionNode()]);

      expect(result.view.isAllowed).toBe(true);
      expect(result.create.isAllowed).toBe(true);
      expect(result.update.isAllowed).toBe(true);
      expect(result.delete.isAllowed).toBe(true);
    });

    test("returns denied with message for DENY actions", () => {
      const result = getPermission([createPermissionNode({ create: "DENY", delete: "DENY" })]);

      expect(result.view.isAllowed).toBe(true);
      expect(result.create.isAllowed).toBe(false);
      expect(result.update.isAllowed).toBe(true);
      expect(result.delete.isAllowed).toBe(false);
    });

    test("returns allowed if any permission node has ALLOW", () => {
      const result = getPermission([
        createPermissionNode({ update: "DENY" }),
        createPermissionNode({ update: "ALLOW" }),
      ]);

      expect(result.update.isAllowed).toBe(true);
    });
  });

  describe("with branch OPEN", () => {
    test("does not override permissions when branch is OPEN", () => {
      const result = getPermission([createPermissionNode()], {
        branch: { status: BRANCH_STATUS.OPEN },
        schema: awareSchema,
      });

      expect(result.view.isAllowed).toBe(true);
      expect(result.create.isAllowed).toBe(true);
      expect(result.update.isAllowed).toBe(true);
      expect(result.delete.isAllowed).toBe(true);
    });

    test("does not override PERMISSION_ALLOW_ALL when branch is OPEN", () => {
      const result = getPermission(undefined, {
        branch: { status: BRANCH_STATUS.OPEN },
        schema: awareSchema,
      });

      expect(result).toEqual(PERMISSION_ALLOW_ALL);
    });
  });

  describe("with branch MERGED", () => {
    test("denies create/update/delete for branch-aware objects", () => {
      const result = getPermission([createPermissionNode()], {
        branch: { status: BRANCH_STATUS.MERGED },
        schema: awareSchema,
      });

      expect(result.view.isAllowed).toBe(true);
      expect(result.create.isAllowed).toBe(false);
      expect(result.create).toHaveProperty("message", "Cannot edit objects on a merged branch");
      expect(result.update.isAllowed).toBe(false);
      expect(result.update).toHaveProperty("message", "Cannot edit objects on a merged branch");
      expect(result.delete.isAllowed).toBe(false);
      expect(result.delete).toHaveProperty("message", "Cannot edit objects on a merged branch");
    });

    test("denies create/update/delete for branch-local objects", () => {
      const result = getPermission([createPermissionNode()], {
        branch: { status: BRANCH_STATUS.MERGED },
        schema: localSchema,
      });

      expect(result.view.isAllowed).toBe(true);
      expect(result.create.isAllowed).toBe(false);
      expect(result.update.isAllowed).toBe(false);
      expect(result.delete.isAllowed).toBe(false);
    });

    test("does NOT deny for branch-agnostic objects", () => {
      const result = getPermission([createPermissionNode()], {
        branch: { status: BRANCH_STATUS.MERGED },
        schema: agnosticSchema,
      });

      expect(result.view.isAllowed).toBe(true);
      expect(result.create.isAllowed).toBe(true);
      expect(result.update.isAllowed).toBe(true);
      expect(result.delete.isAllowed).toBe(true);
    });

    test("denies when no permission data (PERMISSION_ALLOW_ALL) on merged branch", () => {
      const result = getPermission(undefined, {
        branch: { status: BRANCH_STATUS.MERGED },
        schema: awareSchema,
      });

      expect(result.view.isAllowed).toBe(true);
      expect(result.create.isAllowed).toBe(false);
      expect(result.update.isAllowed).toBe(false);
      expect(result.delete.isAllowed).toBe(false);
    });

    test("denies when no schema provided (safe default)", () => {
      const result = getPermission(undefined, {
        branch: { status: BRANCH_STATUS.MERGED },
      });

      expect(result.view.isAllowed).toBe(true);
      expect(result.create.isAllowed).toBe(false);
      expect(result.update.isAllowed).toBe(false);
      expect(result.delete.isAllowed).toBe(false);
    });

    test("merged override takes priority over ALLOW permission data", () => {
      const result = getPermission([createPermissionNode()], {
        branch: { status: BRANCH_STATUS.MERGED },
        schema: awareSchema,
      });

      expect(result.create.isAllowed).toBe(false);
      expect(result.update.isAllowed).toBe(false);
      expect(result.delete.isAllowed).toBe(false);
    });

    test("view is never overridden even on merged branch", () => {
      const result = getPermission([createPermissionNode({ view: "ALLOW" })], {
        branch: { status: BRANCH_STATUS.MERGED },
        schema: awareSchema,
      });

      expect(result.view.isAllowed).toBe(true);
    });
  });

  describe("getMessage", () => {
    test("returns DENY message", () => {
      const result = getPermission([createPermissionNode({ create: "DENY" })]);

      expect(result.create.isAllowed).toBe(false);
      expect(result.create).toHaveProperty(
        "message",
        "You don't have permission to create this object."
      );
    });

    test("returns ALLOW_DEFAULT message", () => {
      const result = getPermission([createPermissionNode({ update: "ALLOW_DEFAULT" })]);

      expect(result.update.isAllowed).toBe(false);
      expect(result.update).toHaveProperty(
        "message",
        "This action is only allowed on the default branch. Please switch to the default branch to update this object."
      );
    });

    test("returns ALLOW_OTHER message", () => {
      const result = getPermission([createPermissionNode({ delete: "ALLOW_OTHER" })]);

      expect(result.delete.isAllowed).toBe(false);
      expect(result.delete).toHaveProperty(
        "message",
        "This action is not allowed on the default branch. Please switch to a different branch to delete this object."
      );
    });
  });
});
