import { describe, expect, it } from "vitest";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import { PROPOSED_CHANGES_THREAD_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change-thread";

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
    const sort: Sort[] = [{ field: "node_metadata__created_at", direction: "DESC" }];
    const params = {
      filters,
      sort,
    };

    // WHEN
    const result = proposedChangesQueryKeys.list(params);

    // THEN
    expect(result).toEqual(["objects", PROPOSED_CHANGE_OBJECT, filters, sort]);
  });

  it("returns a different list query key per sort", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "status__value", value: "open" }];

    // WHEN
    const newestFirst = proposedChangesQueryKeys.list({
      filters,
      sort: [{ field: "node_metadata__created_at", direction: "DESC" }],
    });
    const oldestFirst = proposedChangesQueryKeys.list({
      filters,
      sort: [{ field: "node_metadata__created_at", direction: "ASC" }],
    });

    // THEN
    expect(newestFirst).not.toEqual(oldestFirst);
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
