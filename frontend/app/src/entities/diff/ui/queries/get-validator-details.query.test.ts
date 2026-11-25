import { describe, expect, test } from "vitest";

import { getValidatorDetailsQueryOptions } from "./get-validator-details.query";

describe("validator details query caching", () => {
  test("keeps failed-first, default artifact and generic results in separate cache entries", () => {
    // GIVEN
    const params = { ids: ["validator"], checksOffset: 0, checksLimit: 10 };

    // WHEN
    const failedFirst = getValidatorDetailsQueryOptions({ ...params, checksFailedFirst: true });
    const defaultArtifact = getValidatorDetailsQueryOptions({
      ...params,
      checksFailedFirst: false,
    });
    const generic = getValidatorDetailsQueryOptions(params);

    // THEN
    expect(failedFirst.queryKey).not.toEqual(defaultArtifact.queryKey);
    expect(failedFirst.queryKey).not.toEqual(generic.queryKey);
    expect(defaultArtifact.queryKey).not.toEqual(generic.queryKey);
  });
});
