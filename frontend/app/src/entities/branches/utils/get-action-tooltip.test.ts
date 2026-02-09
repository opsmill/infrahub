import { describe, expect, test } from "vitest";

import { BRANCH_STATUS } from "@/entities/branches/constants";

import { getActionAvailability } from "./get-action-tooltip";

describe("getActionAvailability", () => {
  describe("branch merged scenarios", () => {
    test("disables action when branch is merged, even if permission allows", () => {
      // GIVEN
      const permission = { isAllowed: true, message: undefined };

      // WHEN
      const result = getActionAvailability(BRANCH_STATUS.MERGED, permission);

      // THEN
      expect(result.isAllowed).toBe(false);
      expect(result.tooltipMessage).toBe("Cannot edit objects on a merged branch");
    });

    test("shows merged message with priority over permission message", () => {
      // GIVEN
      const permission = { isAllowed: false, message: "You don't have permission" };

      // WHEN
      const result = getActionAvailability(BRANCH_STATUS.MERGED, permission);

      // THEN
      expect(result.isAllowed).toBe(false);
      expect(result.tooltipMessage).toBe("Cannot edit objects on a merged branch");
      expect(result.tooltipMessage).not.toBe("You don't have permission");
    });
  });

  describe("permission denied scenarios", () => {
    test("disables action when permission denied on open branch", () => {
      // GIVEN
      const permission = { isAllowed: false, message: "You don't have permission to create" };

      // WHEN
      const result = getActionAvailability(BRANCH_STATUS.OPEN, permission);

      // THEN
      expect(result.isAllowed).toBe(false);
      expect(result.tooltipMessage).toBe("You don't have permission to create");
    });

    test("shows permission message on open branch", () => {
      // GIVEN
      const permission = { isAllowed: false, message: "You don't have permission to update" };

      // WHEN
      const result = getActionAvailability(BRANCH_STATUS.OPEN, permission);

      // THEN
      expect(result.isAllowed).toBe(false);
      expect(result.tooltipMessage).toBe("You don't have permission to update");
    });
  });

  describe("action allowed scenarios", () => {
    test("enables action when branch is open and permission allows", () => {
      // GIVEN
      const permission = { isAllowed: true, message: undefined };

      // WHEN
      const result = getActionAvailability(BRANCH_STATUS.OPEN, permission);

      // THEN
      expect(result.isAllowed).toBe(true);
      expect(result.tooltipMessage).toBeUndefined();
    });

    test("enables action on other branch statuses when permission allows", () => {
      // GIVEN
      const permission = { isAllowed: true, message: undefined };

      // WHEN / THEN
      expect(getActionAvailability(BRANCH_STATUS.NEED_REBASE, permission).isAllowed).toBe(true);
      expect(getActionAvailability(BRANCH_STATUS.NEED_UPGRADE_REBASE, permission).isAllowed).toBe(
        true
      );
      expect(getActionAvailability(BRANCH_STATUS.DELETING, permission).isAllowed).toBe(true);
    });

    test("returns no tooltip when action is allowed", () => {
      // GIVEN
      const permission = { isAllowed: true, message: undefined };

      // WHEN
      const result = getActionAvailability(BRANCH_STATUS.OPEN, permission);

      // THEN
      expect(result.tooltipMessage).toBeUndefined();
    });
  });

  describe("priority order", () => {
    test("merged status takes priority over permission", () => {
      // GIVEN - both permission denied and branch merged
      const permission = { isAllowed: false, message: "Permission denied" };

      // WHEN
      const result = getActionAvailability(BRANCH_STATUS.MERGED, permission);

      // THEN - merged message shown, not permission message
      expect(result.isAllowed).toBe(false);
      expect(result.tooltipMessage).toBe("Cannot edit objects on a merged branch");
    });
  });
});
