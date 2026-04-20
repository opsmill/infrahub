import { describe, expect, it } from "vitest";

import { globalDecisionOptions, objectDecisionOptions } from "@/entities/role-manager/constants";
import { getDecisionOptions } from "@/entities/role-manager/domain/get-decision-options";

describe("getDecisionOptions", () => {
  it("returns objectDecisionOptions for CoreObjectPermission decision", () => {
    // GIVEN
    const schemaKind = "CoreObjectPermission";
    const attributeName = "decision";

    // WHEN
    const result = getDecisionOptions(schemaKind, attributeName);

    // THEN
    expect(result).toBe(objectDecisionOptions);
  });

  it("returns globalDecisionOptions for CoreGlobalPermission decision", () => {
    // GIVEN
    const schemaKind = "CoreGlobalPermission";
    const attributeName = "decision";

    // WHEN
    const result = getDecisionOptions(schemaKind, attributeName);

    // THEN
    expect(result).toBe(globalDecisionOptions);
  });

  it("returns null when attributeName is not 'decision'", () => {
    // GIVEN
    const schemaKind = "CoreObjectPermission";
    const attributeName = "action";

    // WHEN
    const result = getDecisionOptions(schemaKind, attributeName);

    // THEN
    expect(result).toBeNull();
  });

  it("returns null for a non-permission schema kind", () => {
    // GIVEN
    const schemaKind = "CoreAccount";
    const attributeName = "decision";

    // WHEN
    const result = getDecisionOptions(schemaKind, attributeName);

    // THEN
    expect(result).toBeNull();
  });

  it("returns null when schemaKind is undefined", () => {
    // GIVEN / WHEN
    const result = getDecisionOptions(undefined, "decision");

    // THEN
    expect(result).toBeNull();
  });
});
