import { describe, expect, test } from "vitest";

import { formValuesToParams, paramsToFormValues } from "./use-dependencies-mode-params";

describe("paramsToFormValues", () => {
  test("maps URL params to form values", () => {
    expect(
      paramsToFormValues({
        source: "src-id",
        targetKinds: ["InfraDevice", "InfraInterface"],
        depth: 8,
      })
    ).toEqual({
      sourceId: "src-id",
      targetKinds: ["InfraDevice", "InfraInterface"],
      maxDepth: 8,
    });
  });
});

describe("formValuesToParams", () => {
  test("maps form values to URL param updates", () => {
    expect(
      formValuesToParams({
        sourceId: "src-id",
        targetKinds: ["InfraDevice"],
        maxDepth: 3,
      })
    ).toEqual({
      source: "src-id",
      targetKinds: ["InfraDevice"],
      depth: 3,
    });
  });
});
