import { describe, expect, it } from "vitest";

import type { ProfileSchema } from "@/entities/schema/types";

import { isSourceFromProfile } from "./is-source-from-profile";

describe("isSourceFromProfile", () => {
  const profileSchemas: ProfileSchema[] = [
    { kind: "ProfileBuiltinTag", namespace: "Profile" } as ProfileSchema,
    { kind: "ProfileTestDevice", namespace: "Profile" } as ProfileSchema,
  ];

  it("returns true when source typename matches a profile schema kind", () => {
    expect(isSourceFromProfile("ProfileBuiltinTag", profileSchemas)).toBe(true);
    expect(isSourceFromProfile("ProfileTestDevice", profileSchemas)).toBe(true);
  });

  it("returns false when source typename does not match any profile schema kind", () => {
    expect(isSourceFromProfile("BuiltinTag", profileSchemas)).toBe(false);
    expect(isSourceFromProfile("TestDevice", profileSchemas)).toBe(false);
    expect(isSourceFromProfile("SomeOtherKind", profileSchemas)).toBe(false);
  });

  it("returns false when source typename is null", () => {
    expect(isSourceFromProfile(null, profileSchemas)).toBe(false);
  });

  it("returns false when source typename is undefined", () => {
    expect(isSourceFromProfile(undefined, profileSchemas)).toBe(false);
  });

  it("returns false when profile schemas list is empty", () => {
    expect(isSourceFromProfile("ProfileBuiltinTag", [])).toBe(false);
  });
});
