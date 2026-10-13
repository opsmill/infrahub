import { describe, expect, it } from "vitest";

import { CHECKS_LABEL } from "@/entities/diff/ui/checks/checks-labels";

import { getValidatorsStats } from "./checks";

const generateValidator = (state: string, conclusion: string) => ({
  state: { value: state },
  conclusion: { value: conclusion },
});

describe("getValidatorsStats", () => {
  it("counts the skipped validators apart from the successful ones", () => {
    // GIVEN
    const validators = [
      generateValidator("completed", "success"),
      generateValidator("completed", "skipped"),
      generateValidator("completed", "skipped"),
    ];

    // WHEN
    const stats = getValidatorsStats(validators);

    // THEN
    expect(stats).toEqual([
      { name: CHECKS_LABEL.SUCCESS, value: 1, className: "fill-green-400" },
      { name: CHECKS_LABEL.SKIPPED, value: 2, className: "fill-blue-400" },
    ]);
  });

  it("does not report a proposed change with only skipped validators as empty", () => {
    // GIVEN
    const validators = [generateValidator("completed", "skipped")];

    // WHEN
    const stats = getValidatorsStats(validators);

    // THEN
    expect(stats).toEqual([{ name: CHECKS_LABEL.SKIPPED, value: 1, className: "fill-blue-400" }]);
  });

  it("does not count a validator in progress as skipped", () => {
    // GIVEN
    const validators = [generateValidator("in_progress", "skipped")];

    // WHEN
    const stats = getValidatorsStats(validators);

    // THEN
    expect(stats).toEqual([
      { name: CHECKS_LABEL.IN_PROGRESS, value: 1, className: "fill-orange-400" },
    ]);
  });
});
