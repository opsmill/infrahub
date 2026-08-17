import { describe, expect, test } from "vitest";

import { generateRandomBranchName } from "./utils";

// Guards the invariant the helper's comment describes. Prose alone already failed once: this
// helper and its Python counterpart silently diverged despite the Python one documenting itself
// as a port, which is how the base36 alphabet survived long enough to spell "save" in a branch
// name and collide with getByRole("button", { name: "Save" }).
const HEX_SUFFIX = /^[0-9a-f]{12}$/;
const SAMPLE_SIZE = 1000;

describe("generateRandomBranchName", () => {
  test("suffixes a prefix with hex only", () => {
    // GIVEN
    const prefix = "object-relationships";

    // WHEN
    const suffixes = Array.from({ length: SAMPLE_SIZE }, () =>
      generateRandomBranchName(prefix).slice(prefix.length)
    );

    // THEN
    expect(suffixes.filter((suffix) => !HEX_SUFFIX.test(suffix))).toEqual([]);
  });

  test("returns hex only when no prefix is given", () => {
    // GIVEN
    const noPrefix = undefined;

    // WHEN
    const names = Array.from({ length: SAMPLE_SIZE }, () => generateRandomBranchName(noPrefix));

    // THEN
    expect(names.filter((name) => !HEX_SUFFIX.test(name))).toEqual([]);
  });
});
