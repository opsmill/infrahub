import { describe, expect, it } from "vitest";

import { PROPOSED_CHANGES_THREAD_OBJECT } from "@/config/constants";

import type { Filter } from "@/shared/hooks/useFilters";

import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";

import { proposedChangesQueryKeys } from "./proposed-changes.query-keys";

describe("proposedChangesQueryKeys", () => {
  it("returns base query key for all", () => {
    // WHEN
    const result = proposedChangesQueryKeys.all;

    // THEN
    expect(result).toEqual(["objects", PROPOSED_CHANGE_OBJECT]);
  });

  it("returns query key for list", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "status__value", value: "open" }];
    const params = {
      filters,
    };

    // WHEN
    const result = proposedChangesQueryKeys.list(params);

    // THEN
    expect(result).toEqual(["objects", PROPOSED_CHANGE_OBJECT, filters]);
  });

  it("returns query key for count", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "name__value", value: "abc" }];
    const params = {
      filters,
    };

    // WHEN
    const result = proposedChangesQueryKeys.count(params);

    // THEN
    expect(result).toEqual(["objects", PROPOSED_CHANGE_OBJECT, "count", filters]);
  });

  it("returns query key for detail", () => {
    // GIVEN
    const proposedChangeId = "123";

    // WHEN
    const result = proposedChangesQueryKeys.detail(proposedChangeId);

    // THEN
    expect(result).toEqual(["objects", PROPOSED_CHANGE_OBJECT, proposedChangeId]);
  });

  it("returns query key for actions", () => {
    // GIVEN
    const proposedChangeId = "123";

    // WHEN
    const result = proposedChangesQueryKeys.actions(proposedChangeId);

    // THEN
    expect(result).toEqual(["objects", PROPOSED_CHANGE_OBJECT, proposedChangeId, "actions"]);
  });

  it("returns query key for thread", () => {
    // GIVEN
    const threadId = "456";

    // WHEN
    const result = proposedChangesQueryKeys.thread(threadId);

    // THEN
    expect(result).toEqual(["objects", PROPOSED_CHANGES_THREAD_OBJECT, threadId]);
  });
});
