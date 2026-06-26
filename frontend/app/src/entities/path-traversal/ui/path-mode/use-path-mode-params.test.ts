import { describe, expect, test } from "vitest";

import { formValuesToParams, paramsToFormValues } from "./use-path-mode-params";

describe("paramsToFormValues", () => {
  test("maps URL params to form values", () => {
    expect(
      paramsToFormValues({
        source: "src-id",
        destination: "dst-id",
        depth: 7,
        maxPaths: 25,
        kindFilter: ["InfraDevice"],
        excludedKinds: ["InfraInterface"],
        selectedPath: 3,
      })
    ).toEqual({
      sourceId: "src-id",
      destinationId: "dst-id",
      maxDepth: 7,
      maxPaths: 25,
      kindFilter: ["InfraDevice"],
      excludedKinds: ["InfraInterface"],
    });
  });
});

describe("formValuesToParams", () => {
  test("maps form values to URL param updates and resets selectedPath", () => {
    expect(
      formValuesToParams({
        sourceId: "src-id",
        destinationId: "dst-id",
        maxDepth: 4,
        maxPaths: 12,
        kindFilter: ["InfraDevice"],
        excludedKinds: [],
      })
    ).toEqual({
      source: "src-id",
      destination: "dst-id",
      depth: 4,
      maxPaths: 12,
      kindFilter: ["InfraDevice"],
      excludedKinds: [],
      selectedPath: 0,
    });
  });
});
